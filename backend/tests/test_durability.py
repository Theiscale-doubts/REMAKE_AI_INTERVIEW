"""Tests for the two must-fix issues.

P0: error responses must not be mistaken for success (frontend contract).
P1: broken durable storage must be visible, not silent.
"""
import os
import sys
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="voxhire-dur-")
os.environ["DATA_DIR"] = _TMP
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["ADMIN_PASSWORD"] = "test-admin-pw"

from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402
from app import storage as tools  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    main._rate_buckets.clear()
    main._session_qa.clear()
    main._eval_store.clear()
    monkeypatch.setattr(main, "save_qa_tool", lambda *a, **k: "stubbed")
    monkeypatch.setattr(main, "record_score", lambda *a, **k: "stubbed")
    yield


@pytest.fixture
def client(monkeypatch):
    # Don't hit the network during the startup Sheets check.
    monkeypatch.setattr(main, "verify_sheets", lambda: {"reachable": True, "configured": True,
                                                        "detail": "stubbed", "checked_at": "now"})
    with TestClient(main.app) as c:
        yield c


def _ip(n):
    return {"X-Forwarded-For": f"10.9.0.{n}"}


# ── P0: error responses carry a machine-readable detail ───────────────────

def test_every_error_response_has_a_detail_field(client):
    """The frontend reads `detail`; without it the UI has nothing to show."""
    cases = [
        client.get("/api/start", headers=_ip(1)),                                  # 401
        client.get("/api/log/" + "x" * 200, headers=_ip(2)),                       # 400
        client.post("/api/admin/verify", json={"password": "no"}, headers=_ip(3)),  # 401
    ]
    for r in cases:
        assert r.status_code >= 400
        assert isinstance(r.json().get("detail"), str) and r.json()["detail"], r.text


def test_rate_limit_sends_retry_after_so_the_client_can_back_off(client):
    r = None
    for _ in range(20):
        r = client.get("/api/start?code=BAD", headers=_ip(4))
        if r.status_code == 429:
            break
    assert r.status_code == 429
    assert r.headers.get("Retry-After"), "429 must tell the client how long to wait"


def test_chat_failure_is_a_real_error_status_not_a_200(client, monkeypatch):
    """A failed turn must be a non-2xx, or the frontend renders a blank question."""
    def _explode(**kwargs):
        raise RuntimeError("provider down")
    monkeypatch.setattr(main, "run_agent_turn", _explode)
    r = client.post("/api/chat", json={"session_id": "s", "message": "an answer"}, headers=_ip(5))
    assert r.status_code == 502
    assert "question" not in r.json()


# ── P0: save idempotency (client retries must not duplicate answers) ───────

def _save(client, ip, question="Q1?", answer="A1.", session="dup-sess"):
    return client.post("/api/save", json={
        "question": question, "answer": answer, "session_id": session,
    }, headers=_ip(ip))


def test_identical_retry_does_not_duplicate_the_answer(client):
    assert _save(client, 10).status_code == 200
    r = _save(client, 10)          # the retry
    assert r.status_code == 200
    assert r.json().get("duplicate") is True
    assert len(main._session_qa["dup-sess"]) == 1, "retry must not append a second copy"


def test_a_genuinely_new_answer_is_still_appended(client):
    _save(client, 11, question="Q1?", answer="A1.")
    _save(client, 11, question="Q2?", answer="A2.")
    assert len(main._session_qa["dup-sess"]) == 2


def test_same_question_with_a_corrected_answer_is_appended(client):
    """A retake changes the answer text — that is not a duplicate."""
    _save(client, 12, question="Q1?", answer="first attempt")
    _save(client, 12, question="Q1?", answer="corrected attempt")
    assert len(main._session_qa["dup-sess"]) == 2


# ── P1: durable-storage visibility ────────────────────────────────────────

def test_healthz_reports_durable_storage(client):
    body = client.get("/api/healthz", headers=_ip(20)).json()
    assert "durable_storage" in body
    assert set(body["durable_storage"]) >= {"configured", "reachable", "detail"}


def test_healthz_is_degraded_when_storage_is_unreachable(client, monkeypatch):
    monkeypatch.setattr(main, "sheets_status", lambda: {
        "configured": True, "reachable": False, "detail": "boom", "checked_at": "now"})
    body = client.get("/api/healthz", headers=_ip(21)).json()
    assert body["status"] == "degraded"
    assert body["durable_storage"]["reachable"] is False


def test_healthz_is_ok_when_storage_is_reachable(client, monkeypatch):
    monkeypatch.setattr(main, "sheets_status", lambda: {
        "configured": True, "reachable": True, "detail": "fine", "checked_at": "now"})
    assert client.get("/api/healthz", headers=_ip(22)).json()["status"] == "ok"


def test_healthz_exposes_no_secrets(client):
    text = client.get("/api/healthz", headers=_ip(23)).text.lower()
    for leak in ("api_key", "password", "private_key", "client_email", "token"):
        assert leak not in text


def test_unconfigured_credentials_report_unreachable(monkeypatch):
    monkeypatch.setattr(tools, "_creds", None)
    status = tools.verify_sheets()
    assert status["reachable"] is False
    assert status["configured"] is False
    assert "wiped" in status["detail"] or "ONLY on local disk" in status["detail"]


def test_a_failed_sheet_write_marks_storage_unreachable(monkeypatch):
    """Storage healthy at boot can break later; healthz must track that."""
    class Boom:
        def __getattr__(self, _):
            raise RuntimeError("quota exceeded")
    monkeypatch.setattr(tools, "_creds", object())
    monkeypatch.setattr(tools, "_get_sheet", lambda username="Interview": Boom())
    tools._sheets_status.update(reachable=True, detail="was fine")
    tools._sync_sheet({"Session_id": "s"})
    assert tools.sheets_status()["reachable"] is False
    assert "last write failed" in tools.sheets_status()["detail"]


def test_startup_check_never_prevents_boot(monkeypatch):
    """A storage check that throws must not take the service down."""
    def _boom():
        raise RuntimeError("network unreachable")
    monkeypatch.setattr(main, "verify_sheets", _boom)   # never reaches the network
    with TestClient(main.app) as c:
        assert c.get("/api/check", headers=_ip(30)).status_code == 200
