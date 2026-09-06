"""Tests for the durable-storage hardening and the admin results lookup.

Google Sheets is stubbed throughout — no network. Run with
    ./venv/bin/python -m pytest test_results_lookup.py -v
"""
import os
import sys
import tempfile
import time

import pytest

_TMP = tempfile.mkdtemp(prefix="voxhire-results-")
os.environ["DATA_DIR"] = _TMP
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["ADMIN_PASSWORD"] = "test-admin-pw"

from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402
from app import storage as tools  # noqa: E402


def _row(session_id, name, email, role, score="", answered="3", updated="2026-09-06 10:00:00"):
    row = tools._blank_row(session_id)
    row.update(Name=name, Email=email, Role=role, Score=score,
               QuestionsAnswered=answered, UpdatedAt=updated)
    return row


SAMPLE = [
    _row("11111111-aaaa", "Akshat Trivedi", "akshat@example.com", "ai_engineer", "7.2", "9", "2026-09-06 12:00:00"),
    _row("22222222-bbbb", "Priya Sharma", "priya@example.com", "data_analytics", "5.8", "9", "2026-09-05 09:00:00"),
    _row("33333333-cccc", "Sam Okafor", "sam@example.com", "datascience", "", "4", "2026-09-04 08:00:00"),
]


@pytest.fixture(autouse=True)
def _stub_sheet(monkeypatch):
    tools.invalidate_rows_cache()
    monkeypatch.setattr(tools, "_creds", object())
    monkeypatch.setattr(tools, "_rows_from_sheet", lambda: [dict(r) for r in SAMPLE])
    with tools._pending_lock:
        tools._pending_writes.clear()
    yield
    tools.invalidate_rows_cache()


@pytest.fixture
def client(monkeypatch):
    _healthy = {"configured": True, "reachable": True, "detail": "stubbed", "checked_at": "test"}
    monkeypatch.setattr(main, "verify_sheets", lambda: _healthy)
    monkeypatch.setattr(main, "sheets_status", lambda: _healthy)
    with TestClient(main.app) as c:
        yield c


def _token(client, ip=1):
    return client.post("/api/admin/verify", json={"password": "test-admin-pw"},
                       headers={"X-Forwarded-For": f"10.5.0.{ip}"}).json()["token"]


def _hdr(tok, ip=1):
    return {"X-Admin-Token": tok, "X-Forwarded-For": f"10.5.0.{ip}"}


# ── Search behaviour ──────────────────────────────────────────────────────

def test_empty_query_returns_every_interview():
    r = tools.search_sessions()
    assert r["total"] == 3
    assert {x["name"] for x in r["results"]} == {"Akshat Trivedi", "Priya Sharma", "Sam Okafor"}


@pytest.mark.parametrize("query,expected", [
    ("akshat", "Akshat Trivedi"),
    ("AKSHAT", "Akshat Trivedi"),          # case-insensitive
    ("priya@example.com", "Priya Sharma"),  # by email
    ("okafor", "Sam Okafor"),               # by surname
    ("33333333", "Sam Okafor"),             # by session id fragment
])
def test_search_finds_by_any_field(query, expected):
    r = tools.search_sessions(query=query)
    assert r["total"] == 1
    assert r["results"][0]["name"] == expected


def test_search_by_role_returns_that_role_only():
    r = tools.search_sessions(query="data_analytics")
    assert [x["name"] for x in r["results"]] == ["Priya Sharma"]


def test_no_match_returns_empty_not_an_error():
    r = tools.search_sessions(query="nobody-by-that-name")
    assert r["total"] == 0 and r["results"] == []


def test_results_are_newest_first():
    names = [x["name"] for x in tools.search_sessions()["results"]]
    assert names == ["Akshat Trivedi", "Priya Sharma", "Sam Okafor"]


def test_unscored_interview_still_listed_with_null_score():
    sam = [x for x in tools.search_sessions()["results"] if x["name"] == "Sam Okafor"][0]
    assert sam["score"] is None
    assert sam["questions_answered"] == 4


def test_summary_omits_the_photo_and_transcript():
    row = tools.search_sessions()["results"][0]
    assert "photo" not in row and "Photo" not in row
    assert not any(k.startswith("Q") or k.startswith("A") for k in row)
    assert row["has_photo"] is False


def test_pagination():
    page1 = tools.search_sessions(limit=2, offset=0)
    page2 = tools.search_sessions(limit=2, offset=2)
    assert len(page1["results"]) == 2 and len(page2["results"]) == 1
    assert page1["total"] == page2["total"] == 3


# ── The corruption that was actually in the live sheet ────────────────────

def test_stale_header_rows_are_not_listed_as_interviews(monkeypatch):
    """Older migrations inserted extra header rows into the data region."""
    legacy = ["Question", "Answer", "Session_id", "Name", "Email", "Role"]
    monkeypatch.setattr(tools, "_rows_from_sheet",
                        lambda: [dict(zip(tools.CSV_HEADERS, legacy))] + [dict(r) for r in SAMPLE])
    tools.invalidate_rows_cache()
    names = [x["name"] for x in tools.search_sessions()["results"]]
    assert "Answer" not in names, "a stray header row was listed as a candidate"
    assert len(names) == 3


@pytest.mark.parametrize("token", ["Question", "Answer", "Session_id", "Timestamp", ""])
def test_header_tokens_are_never_interview_rows(token):
    assert tools._is_interview_row([token]) is False


def test_a_real_session_id_is_an_interview_row():
    assert tools._is_interview_row(["11111111-aaaa-bbbb"]) is True


# ── Caching ───────────────────────────────────────────────────────────────

def test_reads_are_cached_not_refetched_per_call(monkeypatch):
    calls = {"n": 0}

    def _counting():
        calls["n"] += 1
        return [dict(r) for r in SAMPLE]

    monkeypatch.setattr(tools, "_rows_from_sheet", _counting)
    tools.invalidate_rows_cache()
    for _ in range(10):
        tools.search_sessions(query="akshat")
    assert calls["n"] == 1, f"cache miss: {calls['n']} sheet fetches for 10 searches"


def test_force_bypasses_the_cache(monkeypatch):
    calls = {"n": 0}

    def _counting():
        calls["n"] += 1
        return [dict(r) for r in SAMPLE]

    monkeypatch.setattr(tools, "_rows_from_sheet", _counting)
    tools.invalidate_rows_cache()
    tools.search_sessions()
    tools.search_sessions(force=True)
    assert calls["n"] == 2


def test_falls_back_to_local_csv_when_sheets_is_down(monkeypatch):
    monkeypatch.setattr(tools, "_rows_from_sheet", lambda: None)
    monkeypatch.setattr(tools, "_read_csv_rows", lambda p: [dict(SAMPLE[0])])
    tools.invalidate_rows_cache()
    r = tools.search_sessions()
    assert r["source"] == "csv"
    assert r["durable"] is False, "a local-only copy must not claim to be durable"
    assert r["total"] == 1


# ── Write-behind queue (the Option A durability fix) ──────────────────────

def test_a_failed_write_is_retried_not_dropped(monkeypatch):
    attempts = {"n": 0}

    def _flaky(row, username="Interview"):
        attempts["n"] += 1
        return "data stored" if attempts["n"] >= 3 else "Failed to Add values: boom"

    monkeypatch.setattr(tools, "_sync_sheet_now", _flaky)
    monkeypatch.setattr(tools, "SYNC_BASE_BACKOFF", 0.01)
    tools._enqueue_sync(dict(SAMPLE[0]))

    deadline = time.time() + 5
    while tools.sync_queue_depth() and time.time() < deadline:
        time.sleep(0.05)
    assert attempts["n"] >= 3, "the write was not retried"
    assert tools.sync_queue_depth() == 0, "the row never landed"


def test_pending_writes_are_coalesced_per_session(monkeypatch):
    monkeypatch.setattr(tools, "_sync_sheet_now", lambda row, username="Interview": "failed")
    monkeypatch.setattr(tools, "_ensure_worker", lambda: None)   # inspect the queue, don't drain it
    for i in range(10):
        row = dict(SAMPLE[0]); row["QuestionsAnswered"] = str(i)
        tools._enqueue_sync(row)
    assert tools.sync_queue_depth() == 1, "ten answers should leave one pending write"
    with tools._pending_lock:
        queued = list(tools._pending_writes.values())[0]["row"]
    assert queued["QuestionsAnswered"] == "9", "the queued row must be the latest state"


def test_a_permanently_failing_write_is_dead_lettered(monkeypatch):
    monkeypatch.setattr(tools, "_sync_sheet_now", lambda row, username="Interview": "failed forever")
    monkeypatch.setattr(tools, "SYNC_BASE_BACKOFF", 0.001)
    monkeypatch.setattr(tools, "SYNC_MAX_ATTEMPTS", 2)
    parked = []
    monkeypatch.setattr(tools, "_to_dead_letter", lambda row, reason: parked.append((row, reason)))
    tools._enqueue_sync(dict(SAMPLE[0]))
    deadline = time.time() + 5
    while not parked and time.time() < deadline:
        time.sleep(0.05)
    assert parked, "an unwritable row must be parked, never silently dropped"


def test_the_request_path_does_not_wait_on_sheets(monkeypatch):
    """_sync_sheet must queue and return, not block the candidate."""
    def _slow(row, username="Interview"):
        time.sleep(5)
        return "data stored"

    monkeypatch.setattr(tools, "_sync_sheet_now", _slow)
    monkeypatch.setattr(tools, "_ensure_worker", lambda: None)
    started = time.time()
    assert tools._sync_sheet(dict(SAMPLE[0])) == "queued"
    assert time.time() - started < 0.5, "the request path blocked on a Sheets write"


# ── Endpoint: auth, validation, shape ─────────────────────────────────────

def test_results_endpoint_requires_an_admin_token(client):
    assert client.get("/api/admin/results", headers={"X-Forwarded-For": "10.5.9.1"}).status_code == 401
    assert client.get("/api/admin/results",
                      headers={"X-Admin-Token": "forged", "X-Forwarded-For": "10.5.9.2"}).status_code == 401


def test_results_endpoint_returns_candidates(client):
    tok = _token(client, 2)
    body = client.get("/api/admin/results", headers=_hdr(tok, 2)).json()
    assert body["total"] == 3
    assert "pending_sync" in body
    assert {r["name"] for r in body["results"]} == {"Akshat Trivedi", "Priya Sharma", "Sam Okafor"}


def test_results_endpoint_searches(client):
    tok = _token(client, 3)
    body = client.get("/api/admin/results?q=priya", headers=_hdr(tok, 3)).json()
    assert body["total"] == 1
    assert body["results"][0]["session_id"] == "22222222-bbbb"


def test_results_endpoint_rejects_an_absurd_search_term(client):
    tok = _token(client, 4)
    r = client.get("/api/admin/results?q=" + "x" * 500, headers=_hdr(tok, 4))
    assert r.status_code == 400


def test_results_endpoint_clamps_limit(client):
    tok = _token(client, 5)
    body = client.get("/api/admin/results?limit=99999", headers=_hdr(tok, 5)).json()
    assert body["limit"] <= 200


def test_results_endpoint_is_rate_limited(client):
    tok = _token(client, 6)
    codes = [client.get("/api/admin/results", headers=_hdr(tok, 6)).status_code for _ in range(80)]
    assert 429 in codes


def test_forced_refresh_has_a_tighter_limit(client):
    tok = _token(client, 7)
    codes = [client.get("/api/admin/results?refresh=true", headers=_hdr(tok, 7)).status_code
             for _ in range(20)]
    assert 429 in codes, "an uncached full-sheet fetch must be limited harder"


def test_healthz_surfaces_the_sync_backlog(client):
    body = client.get("/api/healthz", headers={"X-Forwarded-For": "10.5.9.9"}).json()
    assert "pending_sync" in body["durable_storage"]
