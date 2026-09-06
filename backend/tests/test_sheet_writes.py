"""Write-path safety tests against a fake spreadsheet.

These exist because the real write path could corrupt unrelated rows, and that
is not something to discover on production data. A fake sheet lets us assert
exactly which cells were touched.
"""
import os
import sys

import pytest

os.environ["VOXHIRE_SKIP_DOTENV"] = "1"   # never reach the real spreadsheet
from app import storage as tools  # noqa: E402


class FakeSheet:
    """Minimal stand-in for a gspread worksheet, recording every mutation."""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.col_count = 60
        self.ops = []

    def row_values(self, n):
        return list(self.rows[n - 1]) if 0 < n <= len(self.rows) else []

    def col_values(self, n):
        return [(r[n - 1] if len(r) >= n else "") for r in self.rows]

    def append_row(self, values):
        self.ops.append(("append", len(self.rows) + 1))
        self.rows.append(list(values))

    def insert_row(self, values, index):
        self.ops.append(("insert", index))
        self.rows.insert(index - 1, list(values))

    def update(self, values=None, range_name=None, **kw):
        self.ops.append(("update", range_name))
        idx = int("".join(c for c in (range_name or "A1") if c.isdigit()) or 1)
        while len(self.rows) < idx:
            self.rows.append([])
        self.rows[idx - 1] = list(values[0])

    def resize(self, rows=None, cols=None):
        if cols:
            self.col_count = cols


@pytest.fixture(autouse=True)
def _creds(monkeypatch):
    monkeypatch.setattr(tools, "_creds", object())
    yield


def _row(session_id, name="N"):
    r = tools._blank_row(session_id)
    r["Name"] = name
    return r


# ── The corruption bug ────────────────────────────────────────────────────

def test_blank_session_id_never_resolves_to_an_existing_row():
    """It used to match the first EMPTY cell in column A and overwrite it."""
    sheet = FakeSheet([list(tools.CSV_HEADERS), ["", "orphan-data"], ["abc", "real"]])
    assert tools._sheet_row_index(sheet, "") is None
    assert tools._sheet_row_index(sheet, "   ") is None
    assert tools._sheet_row_index(sheet, None) is None


def test_a_row_with_no_session_id_is_refused(monkeypatch):
    sheet = FakeSheet([list(tools.CSV_HEADERS), ["", "precious existing row"]])
    monkeypatch.setattr(tools, "_get_sheet", lambda username=None: sheet)
    before = [list(r) for r in sheet.rows]
    result = tools._sync_sheet_now(_row(""))
    assert "no Session_id" in result
    assert sheet.rows == before, "a row with no id must not touch the sheet at all"


def test_an_existing_session_is_updated_in_place_not_appended(monkeypatch):
    sheet = FakeSheet([list(tools.CSV_HEADERS), ["sess-a"] + [""] * 54])
    monkeypatch.setattr(tools, "_get_sheet", lambda username=None: sheet)
    tools._sync_sheet_now(_row("sess-a", "Updated"))
    assert len(sheet.rows) == 2, "an existing session must not create a second row"
    assert sheet.rows[1][tools.CSV_HEADERS.index("Name")] == "Updated"


def test_a_new_session_is_appended(monkeypatch):
    sheet = FakeSheet([list(tools.CSV_HEADERS)])
    monkeypatch.setattr(tools, "_get_sheet", lambda username=None: sheet)
    tools._sync_sheet_now(_row("sess-new", "Fresh"))
    assert len(sheet.rows) == 2
    assert sheet.rows[1][0] == "sess-new"


def test_writing_one_session_leaves_every_other_row_untouched(monkeypatch):
    others = [["sess-x"] + ["keep-x"] * 54, ["sess-y"] + ["keep-y"] * 54]
    sheet = FakeSheet([list(tools.CSV_HEADERS)] + [list(r) for r in others])
    monkeypatch.setattr(tools, "_get_sheet", lambda username=None: sheet)
    tools._sync_sheet_now(_row("sess-y", "Changed"))
    assert sheet.rows[1] == others[0], "an unrelated row was modified"


# ── Header handling ───────────────────────────────────────────────────────

def test_headers_are_never_inserted_only_updated():
    """insert_row is what left real sheets with stacked duplicate headers."""
    sheet = FakeSheet([["Old", "Header"], ["sess-a", "data"]])
    tools._ensure_sheet_headers(sheet)
    assert not any(op == "insert" for op, _ in sheet.ops), f"inserted a row: {sheet.ops}"
    assert sheet.rows[0] == tools.CSV_HEADERS
    assert sheet.rows[1] == ["sess-a", "data"], "data row must not shift"
    assert len(sheet.rows) == 2, "row count must not grow"


def test_matching_headers_are_left_alone():
    sheet = FakeSheet([list(tools.CSV_HEADERS), ["sess-a"]])
    tools._ensure_sheet_headers(sheet)
    assert sheet.ops == [], "no write should happen when headers already match"


def test_repeated_calls_are_idempotent():
    sheet = FakeSheet([["Old"], ["sess-a"]])
    for _ in range(5):
        tools._ensure_sheet_headers(sheet)
    assert len(sheet.rows) == 2, "repeated checks must not accumulate header rows"


def test_an_empty_sheet_gets_a_header():
    sheet = FakeSheet([])
    tools._ensure_sheet_headers(sheet)
    assert sheet.rows == [list(tools.CSV_HEADERS)]


# ── Production isolation ──────────────────────────────────────────────────

def test_dotenv_is_skipped_when_asked():
    """A test run must not pick up the developer's real credentials."""
    import subprocess
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
           "VOXHIRE_SKIP_DOTENV": "1"}
    proc = subprocess.run(
        [sys.executable, "-c", "from app import storage as t; assert t._creds is None; print('isolated')"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "isolated" in proc.stdout


# ── Data location ─────────────────────────────────────────────────────────

def test_all_runtime_data_lives_under_one_directory():
    """The CSV used to anchor on the backend directory while the JSON stores
    honoured DATA_DIR, so pointing DATA_DIR at a mounted disk moved only half
    the data and silently left the CSV on ephemeral storage."""
    assert tools._csv_file().startswith(tools.DATA_DIR)
    assert tools._dead_letter_path().startswith(tools.DATA_DIR)


def test_data_dir_is_honoured(monkeypatch):
    monkeypatch.setattr(tools, "DATA_DIR", "/tmp/voxhire-somewhere-else")
    assert tools._csv_file() == "/tmp/voxhire-somewhere-else/interview_log.csv"
    assert tools._dead_letter_path() == "/tmp/voxhire-somewhere-else/sheet_dead_letter.jsonl"
