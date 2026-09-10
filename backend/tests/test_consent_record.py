"""Consent must be recorded durably, once, and never silently moved.

The UI gate alone proves nothing after the fact — this column is the evidence
that a given candidate agreed to recording, and when.
"""
from app import main
from app import storage


def _save(sid, **kw):
    storage.save_qa_tool(kw.pop("q", "Q?"), kw.pop("a", "A."), sid,
                         name="Case", email="c@e.com", role="SWE", **kw)


def test_consent_timestamp_is_stored():
    sid = "consent-basic"
    _save(sid, consent_accepted_at="2026-09-10T09:15:00.000Z")
    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    assert row["ConsentAcceptedAt"] == "2026-09-10T09:15:00.000Z"


def test_first_timestamp_wins_and_later_saves_cannot_move_it():
    """Every answer resends it; a retry or a tampered later payload must not
    rewrite the moment consent was actually given."""
    sid = "consent-immutable"
    _save(sid, consent_accepted_at="2026-09-10T09:15:00.000Z")
    _save(sid, consent_accepted_at="2026-09-10T23:59:59.000Z")
    _save(sid, consent_accepted_at="")
    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    assert row["ConsentAcceptedAt"] == "2026-09-10T09:15:00.000Z"


def test_admin_summary_exposes_consent():
    sid = "consent-admin"
    _save(sid, consent_accepted_at="2026-09-10T10:00:00.000Z")
    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    assert storage.session_summary(row)["consent_accepted_at"] == "2026-09-10T10:00:00.000Z"


def test_missing_consent_is_empty_string_not_missing_key():
    """Older interviews predate the column; the admin UI reads it unconditionally."""
    sid = "consent-absent"
    _save(sid)
    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    assert storage.session_summary(row)["consent_accepted_at"] == ""


def test_save_endpoint_accepts_and_persists_consent():
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    sid = "consent-endpoint"
    r = client.post("/api/save", json={
        "question": "Q?", "answer": "A.", "session_id": sid,
        "name": "Case", "email": "c@e.com", "role": "SWE",
        "consent_accepted_at": "2026-09-10T11:22:33.000Z",
    })
    assert r.status_code == 200
    assert main._session_qa[sid][0]["ConsentAcceptedAt"] == "2026-09-10T11:22:33.000Z"


def test_oversized_consent_value_is_rejected():
    """Client-supplied text, so it is length-bounded rather than trusted."""
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    r = client.post("/api/save", json={
        "question": "Q?", "answer": "A.", "session_id": "consent-toolong",
        "consent_accepted_at": "x" * 500,
    })
    assert r.status_code == 422


def test_consent_column_is_last_and_qa_columns_unmoved():
    """New columns go on the tail so no existing sheet row gets re-labelled."""
    assert storage.CSV_HEADERS[-1] == "ConsentAcceptedAt"
    assert storage.CSV_HEADERS[-2] == "CopyAttempts"
    assert storage.CSV_HEADERS.index("Q1") == len(storage.BASE_HEADERS)


def test_formula_injection_in_consent_is_neutralised():
    sid = "consent-injection"
    _save(sid, consent_accepted_at="=HYPERLINK(1)")
    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    assert row["ConsentAcceptedAt"].startswith("'=")
