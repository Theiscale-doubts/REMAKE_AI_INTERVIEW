"""Endpoint tests: auth, rate limits, payload caps, store bounds.

No network: the LLM and Google Sheets layers are stubbed. Run with
    ./venv/bin/python -m pytest test_api.py -v
"""
import os
import sys
import tempfile

import pytest

_TMP = tempfile.mkdtemp(prefix="voxhire-api-test-")
os.environ["DATA_DIR"] = _TMP
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["ADMIN_PASSWORD"] = "test-admin-pw"
os.environ["INVITE_CODES"] = ""

from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """Each test starts with empty rate buckets and stores, and no real I/O."""
    main._rate_buckets.clear()
    main._session_qa.clear()
    main._eval_store.clear()
    main._invite_store.clear()
    main._admin_tokens.clear()
    # Never touch the real CSV / Google Sheet from a test.
    monkeypatch.setattr(main, "save_qa_tool", lambda *a, **k: "stubbed")
    monkeypatch.setattr(main, "record_score", lambda *a, **k: "stubbed")
    yield


@pytest.fixture
def client(monkeypatch):
    # The lifespan verifies Google Sheets at startup; stub it so the suite
    # stays offline and fast (it was making a real API call per test).
    _healthy = {"configured": True, "reachable": True, "detail": "stubbed", "checked_at": "test"}
    monkeypatch.setattr(main, "verify_sheets", lambda: _healthy)
    monkeypatch.setattr(main, "sheets_status", lambda: _healthy)
    with TestClient(main.app) as c:
        yield c


def _ip(n):
    """Distinct client IP so tests don't share rate-limit buckets."""
    return {"X-Forwarded-For": f"10.0.0.{n}"}


# ── Health / basics ───────────────────────────────────────────────────────

def test_check_endpoint(client):
    assert client.get("/api/check", headers=_ip(1)).status_code == 200


def test_healthz_reports_stats_without_secrets(client):
    body = client.get("/api/healthz", headers=_ip(2)).json()
    assert body["status"] == "ok"
    assert {"live_sessions", "stored_sessions", "cached_evaluations"} <= set(body)
    assert not any("key" in k.lower() or "password" in k.lower() for k in body)


def test_security_headers_present(client):
    r = client.get("/api/check", headers=_ip(3))
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


# ── Invite gate ───────────────────────────────────────────────────────────

def test_start_rejects_missing_code_when_gate_enabled(client):
    assert client.get("/api/start", headers=_ip(4)).status_code == 401


def test_start_accepts_a_minted_code_once_only(client):
    tok = client.post("/api/admin/verify", json={"password": "test-admin-pw"}, headers=_ip(5)).json()["token"]
    code = client.post("/api/admin/invite", headers={**_ip(5), "X-Admin-Token": tok}).json()["code"]

    first = client.get(f"/api/start?code={code}", headers=_ip(6))
    assert first.status_code == 200 and first.json()["session_id"]
    # Single-use: the same code must not work twice.
    assert client.get(f"/api/start?code={code}", headers=_ip(7)).status_code == 401


def test_start_is_rate_limited_against_code_bruteforce(client):
    codes = [client.get(f"/api/start?code=WRONG{i:03d}", headers=_ip(8)).status_code for i in range(15)]
    assert 429 in codes, "invite-code guessing must be throttled"


def test_oversized_invite_code_rejected(client):
    r = client.get("/api/start?code=" + "A" * 500, headers=_ip(9))
    assert r.status_code == 400


# ── Admin auth ────────────────────────────────────────────────────────────

def test_admin_wrong_password_rejected(client):
    assert client.post("/api/admin/verify", json={"password": "nope"}, headers=_ip(10)).status_code == 401


def test_admin_bruteforce_is_throttled(client):
    codes = [client.post("/api/admin/verify", json={"password": f"x{i}"}, headers=_ip(11)).status_code for i in range(10)]
    assert 429 in codes


def test_admin_endpoints_require_a_token(client):
    assert client.post("/api/admin/invite", headers=_ip(12)).status_code == 401
    assert client.get("/api/admin/invites", headers=_ip(12)).status_code == 401
    assert client.delete("/api/admin/invite/ABCD1234", headers=_ip(12)).status_code == 401


def test_forged_admin_token_rejected(client):
    h = {**_ip(13), "X-Admin-Token": "forged-token-value"}
    assert client.get("/api/admin/invites", headers=h).status_code == 401


# ── /api/save hardening ───────────────────────────────────────────────────

def _save(client, ip, **over):
    payload = {"question": "Q?", "answer": "A.", "session_id": "sess-1"}
    payload.update(over)
    return client.post("/api/save", json=payload, headers=_ip(ip))


def test_save_accepts_a_normal_answer(client):
    assert _save(client, 20).status_code == 200
    assert len(main._session_qa["sess-1"]) == 1


def test_save_rejects_oversized_text(client):
    r = _save(client, 21, answer="x" * 50_000)
    assert r.status_code == 422


def test_save_rejects_oversized_photo(client):
    r = _save(client, 22, photo="data:image/jpeg;base64," + "A" * 1_000_000)
    assert r.status_code == 422


def test_save_rejects_negative_proctor_counters(client):
    assert _save(client, 23, tab_switches=-5).status_code == 422


def test_save_ignores_non_image_photo(client):
    _save(client, 24, photo="javascript:alert(1)")
    assert not main._session_qa["sess-1"][0].get("Photo")


def test_save_stores_a_valid_photo(client):
    _save(client, 25, photo="data:image/jpeg;base64,AAAA")
    assert main._session_qa["sess-1"][0]["Photo"].startswith("data:image/jpeg")


def test_save_caps_entries_per_session(client, monkeypatch):
    """The per-session entry cap is the bound that holds across IPs and time.

    The per-IP rate limit would otherwise trip first from one client, so lower
    the entry cap here to test the cap itself rather than the rate limiter
    (which has its own test below).
    """
    monkeypatch.setattr(main, "_MAX_ENTRIES_PER_SESSION", 5)
    # Distinct answers: an identical repeat is now treated as a client retry
    # and deduped, which would never reach the cap.
    for i in range(5):
        assert _save(client, 26, question=f"Q{i}?", answer=f"A{i}").status_code == 200
    assert _save(client, 26, question="Q5?", answer="A5").status_code == 409


def test_save_is_rate_limited(client):
    codes = [_save(client, 27, session_id=f"s{i}").status_code for i in range(60)]
    assert 429 in codes


def test_session_store_is_bounded(client, monkeypatch):
    monkeypatch.setattr(main, "_MAX_STORED_SESSIONS", 5)
    for i in range(20):
        client.post("/api/save", json={"question": "q", "answer": "a", "session_id": f"bulk-{i}"}, headers=_ip(28))
    assert len(main._session_qa) <= 5


# ── /api/log ──────────────────────────────────────────────────────────────

def test_log_unknown_session_is_404(client, monkeypatch):
    monkeypatch.setattr(main, "extract_values", lambda **k: "[]")
    assert client.get("/api/log/does-not-exist", headers=_ip(30)).status_code == 404


def test_log_rejects_overlong_session_id(client):
    assert client.get("/api/log/" + "x" * 200, headers=_ip(31)).status_code == 400


def test_log_serves_the_cached_evaluation_without_calling_the_llm(client, monkeypatch):
    main._session_qa["cached"] = [{"Question": "q", "Answer": "a", "Name": "N", "Email": "e@x.com", "Role": "ai_engineer"}]
    main._eval_store["cached"] = {"score": 6.4, "feedback": "## Overall Performance\nfine"}

    def _boom():
        raise AssertionError("LLM must not be called when a cached evaluation exists")
    monkeypatch.setattr(main, "_get_groq", _boom)

    body = client.get("/api/log/cached", headers=_ip(32)).json()
    assert body["score"] == 6.4
    assert body["role"] == "ai_engineer"


def test_log_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(main, "extract_values", lambda **k: "[]")
    codes = [client.get(f"/api/log/none-{i}", headers=_ip(33)).status_code for i in range(30)]
    assert 429 in codes


# ── /api/chat ─────────────────────────────────────────────────────────────

def test_chat_rejects_oversized_message(client):
    r = client.post("/api/chat", json={"session_id": "s", "message": "x" * 50_000}, headers=_ip(40))
    assert r.status_code == 422


def test_chat_returns_503_when_no_llm_is_configured(client, monkeypatch):
    def _no_provider(**kwargs):
        raise main.NoLLMProviderError("none configured")
    monkeypatch.setattr(main, "run_agent_turn", _no_provider)
    r = client.post("/api/chat", json={"session_id": "s", "message": "hello there"}, headers=_ip(41))
    assert r.status_code == 503


def test_chat_does_not_leak_internal_errors(client, monkeypatch):
    def _explode(**kwargs):
        raise RuntimeError("SECRET_INTERNAL_TRACE /etc/passwd")
    monkeypatch.setattr(main, "run_agent_turn", _explode)
    r = client.post("/api/chat", json={"session_id": "s", "message": "hello there"}, headers=_ip(42))
    assert r.status_code == 502
    assert "SECRET_INTERNAL_TRACE" not in r.text


def test_chat_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(main, "run_agent_turn", lambda **k: {"question": "q", "total_questions": 9, "is_last_question": False})
    codes = [client.post("/api/chat", json={"session_id": "s", "message": "a real answer here"}, headers=_ip(43)).status_code for i in range(40)]
    assert 429 in codes


# ── Global protections ────────────────────────────────────────────────────

def test_global_rate_limit_backstop(client):
    codes = [client.get("/api/check", headers=_ip(50)).status_code for _ in range(300)]
    assert 429 in codes


def test_oversized_body_rejected_by_content_length(client):
    r = client.post(
        "/api/save",
        content=b"{}",
        headers={**_ip(51), "Content-Type": "application/json", "Content-Length": str(99 * 1024 * 1024)},
    )
    assert r.status_code == 413


def test_rate_bucket_dict_is_bounded(client, monkeypatch):
    """Spoofed X-Forwarded-For values must not grow the limiter without bound."""
    monkeypatch.setattr(main, "_RATE_MAX_KEYS", 50)
    monkeypatch.setattr(main, "_RATE_PRUNE_INTERVAL", 0.0)
    for i in range(500):
        client.get("/api/check", headers={"X-Forwarded-For": f"192.168.{i // 256}.{i % 256}"})
    assert len(main._rate_buckets) <= 200, len(main._rate_buckets)
