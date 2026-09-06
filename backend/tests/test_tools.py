"""Tests for the CSV / Google Sheets export layer (tools.py).

Google Sheets is stubbed; the CSV is written to a temp dir. Run with
    ./venv/bin/python -m pytest test_tools.py -v
"""
import csv
import os
import sys
import tempfile

import pytest

from app import storage as tools  # noqa: E402


@pytest.fixture
def csv_dir(monkeypatch):
    d = tempfile.mkdtemp(prefix="voxhire-tools-")
    real = tools._upsert_csv

    def _upsert(session_id, question, answer, **meta):
        path = os.path.join(d, "interview_log.csv")
        with tools._csv_lock:
            rows = tools._read_csv_rows(path)
            target = next((r for r in rows if r.get("Session_id") == session_id), None)
            if target is None:
                target = tools._blank_row(session_id)
                rows.append(target)
            tools._apply_answer(target, question, answer, **meta)
            tools._write_csv_rows(path, rows)
            return dict(target)

    monkeypatch.setattr(tools, "_upsert_csv", _upsert)
    monkeypatch.setattr(tools, "_sync_sheet", lambda row, username="Interview": "stubbed")
    return d


# ── The new AllQuestions column ───────────────────────────────────────────

def test_allquestions_column_exists_and_is_early():
    assert "AllQuestions" in tools.CSV_HEADERS
    # Should sit with the summary fields, not buried after 40 Q/A columns.
    assert tools.CSV_HEADERS.index("AllQuestions") < tools.CSV_HEADERS.index("Q1")


def test_allquestions_lists_every_question_numbered():
    row = tools._blank_row("s1")
    asked = ["What is a LEFT JOIN?", "Explain window functions.", "What does GROUP BY do?"]
    for q in asked:
        tools._apply_answer(row, q, "some answer")
    cell = row["AllQuestions"]
    assert cell.splitlines() == [f"{i}. {q}" for i, q in enumerate(asked, 1)]


def test_allquestions_grows_with_the_interview():
    row = tools._blank_row("s2")
    for i in range(1, 10):
        tools._apply_answer(row, f"Question {i}", "a")
        assert len(row["AllQuestions"].splitlines()) == i


def test_allquestions_stays_in_sync_with_questionsanswered():
    row = tools._blank_row("s3")
    for i in range(6):
        tools._apply_answer(row, f"Q{i}", "a")
    assert len(row["AllQuestions"].splitlines()) == int(row["QuestionsAnswered"])


def test_allquestions_is_empty_before_any_question():
    assert tools._blank_row("s4")["AllQuestions"] == ""


def test_allquestions_survives_a_csv_round_trip(csv_dir):
    for q in ("First question?", "Second question?"):
        tools.save_qa_tool(q, "answer", "sess-csv", name="N", email="e@x.com", role="ai_engineer")
    with open(os.path.join(csv_dir, "interview_log.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["AllQuestions"] == "1. First question?\n2. Second question?"


# ── Formula-injection safety ──────────────────────────────────────────────

def test_formula_injection_is_neutralised_in_qa_cells():
    row = tools._blank_row("s5")
    tools._apply_answer(row, "=HYPERLINK(\"http://evil\",\"x\")", "@SUM(A1:A9)")
    assert row["Q1"].startswith("'")
    assert row["A1"].startswith("'")


def test_allquestions_strips_the_injection_guard_for_display():
    """The guard quote is a storage artefact; the summary cell should read clean."""
    row = tools._blank_row("s6")
    tools._apply_answer(row, "=1+1 what does this evaluate to?", "a")
    assert row["AllQuestions"] == "1. =1+1 what does this evaluate to?"


def test_allquestions_cell_stays_under_the_sheets_limit():
    row = tools._blank_row("s7")
    for i in range(tools.MAX_QA_PAIRS):
        tools._apply_answer(row, "x" * 5000, "a")
    assert len(row["AllQuestions"]) <= 45_010


# ── Existing behaviour must not regress ───────────────────────────────────

def test_one_row_per_session_not_per_question(csv_dir):
    for i in range(5):
        tools.save_qa_tool(f"Q{i}", f"A{i}", "sess-single")
    with open(os.path.join(csv_dir, "interview_log.csv"), newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 1


def test_proctor_counters_keep_the_maximum_seen():
    row = tools._blank_row("s8")
    tools._apply_answer(row, "q", "a", tab_switches=5)
    tools._apply_answer(row, "q", "a", tab_switches=2)   # frontend re-sent a lower value
    assert row["TabSwitches"] == "5"


def test_photo_is_never_overwritten():
    row = tools._blank_row("s9")
    tools._apply_answer(row, "q", "a", photo="data:image/jpeg;base64,FIRST")
    tools._apply_answer(row, "q", "a", photo="data:image/jpeg;base64,SECOND")
    assert row["Photo"].endswith("FIRST")


def test_row_expands_back_into_qa_entries():
    row = tools._blank_row("s10")
    tools._apply_answer(row, "Q one", "A one", name="Ann", role="datascience")
    tools._apply_answer(row, "Q two", "A two")
    entries = tools._row_to_qa_list(row)
    assert [e["Question"] for e in entries] == ["Q one", "Q two"]
    assert entries[0]["Name"] == "Ann"


def test_google_auth_replaces_deprecated_oauth2client():
    """oauth2client was archived by Google in 2017; nothing should import it."""
    import ast
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "storage.py")).read()
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(m.startswith("oauth2client") for m in imported), imported
    assert "google.oauth2.service_account" in imported
