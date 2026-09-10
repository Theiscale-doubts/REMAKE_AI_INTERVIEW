"""Proctoring counters must survive the whole path: /api/save -> storage ->
the candidate's report AND the admin results list.

Two regressions motivated these:
  1. session_summary() dropped every counter, so the admin results list — the
     one screen a reviewer uses to judge candidates — showed a score with no
     integrity signal beside it.
  2. Tab switches and blocked copy attempts had been merged into a single
     number, which made it impossible to tell which had actually happened.

Google Sheets is stubbed by conftest (VOXHIRE_SKIP_DOTENV); nothing here
touches the network.
"""
import json

from app import main
from app import storage


def _save(session_id, **counters):
    storage.save_qa_tool(
        counters.pop("question", "Q?"), counters.pop("answer", "A."),
        session_id, name="Case", email="c@e.com", role="SWE", **counters,
    )


def test_counters_reach_the_candidate_report():
    sid = "proctor-report"
    _save(sid, tab_switches=1, copy_attempts=0, face_lost_count=0,
          face_lost_seconds=0, multiple_faces_count=0, movement_events=0)
    _save(sid, tab_switches=4, copy_attempts=5, face_lost_count=2,
          face_lost_seconds=12, multiple_faces_count=1, movement_events=7)

    rows = json.loads(storage._extract_from_csv(sid))
    res = main._build_result(rows, rows[0], 6.5, "## Communication (65%)")

    # Cumulative on the client, so the final report takes the highest seen.
    assert res.tab_switches == 4
    assert res.copy_attempts == 5
    assert res.face_lost_count == 2
    assert res.face_lost_seconds == 12
    assert res.multiple_faces_count == 1
    assert res.movement_events == 7


def test_tab_switches_and_copy_attempts_stay_distinct():
    """Merging them hid which behaviour actually occurred."""
    sid = "proctor-distinct"
    _save(sid, tab_switches=2, copy_attempts=9)
    rows = json.loads(storage._extract_from_csv(sid))
    res = main._build_result(rows, rows[0], 5.0, "")
    assert (res.tab_switches, res.copy_attempts) == (2, 9)


def test_admin_summary_includes_every_counter():
    sid = "proctor-admin"
    _save(sid, tab_switches=3, copy_attempts=4, face_lost_count=1,
          face_lost_seconds=8, multiple_faces_count=2, movement_events=6)

    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    summary = storage.session_summary(row)

    assert summary["tab_switches"] == 3
    assert summary["copy_attempts"] == 4
    assert summary["face_lost_count"] == 1
    assert summary["face_lost_seconds"] == 8
    assert summary["multiple_faces_count"] == 2
    assert summary["movement_events"] == 6


def test_clean_interview_reports_zeros_not_missing_keys():
    """The UI reads these unconditionally; absent keys would render blank."""
    sid = "proctor-clean"
    _save(sid)
    row = next(r for r in storage._read_csv_rows(storage._csv_file())
               if r["Session_id"] == sid)
    summary = storage.session_summary(row)
    for key in ("tab_switches", "copy_attempts", "face_lost_count",
                "face_lost_seconds", "multiple_faces_count", "movement_events"):
        assert summary[key] == 0, key


def test_copy_attempts_column_sits_after_the_qa_pairs():
    """Placement is load-bearing: _ensure_sheet_headers rewrites row 1 in place,
    so inserting a column mid-schema would silently re-label every existing
    sheet row's cells. New columns therefore go after the Q/A block — this
    asserts that invariant rather than pinning CopyAttempts to the very end,
    which stops being true the moment another column is added after it."""
    assert storage.CSV_HEADERS.index("CopyAttempts") > storage.CSV_HEADERS.index("A20")
    # Q/A pairs start immediately after BASE_HEADERS and must not have shifted.
    assert storage.CSV_HEADERS.index("Q1") == len(storage.BASE_HEADERS)


def test_save_endpoint_accepts_and_stores_copy_attempts():
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    sid = "proctor-endpoint"
    r = client.post("/api/save", json={
        "question": "Q?", "answer": "A.", "session_id": sid,
        "name": "Case", "email": "c@e.com", "role": "SWE",
        "tab_switches": 2, "copy_attempts": 7,
    })
    assert r.status_code == 200
    entry = main._session_qa[sid][0]
    assert entry["TabSwitches"] == 2
    assert entry["CopyAttempts"] == 7
