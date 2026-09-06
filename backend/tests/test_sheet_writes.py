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
        self.row_count = 1000
        self.ops = []

    def row_values(self, n):
        return list(self.rows[n - 1]) if 0 < n <= len(self.rows) else []

    def col_values(self, n):
        """Mirrors gspread: trailing empty cells are trimmed off the result.

        This matters — _next_free_row relies on it. A fake that returned the
        full padded column would put the next write below every legacy junk
        row instead of directly under the header.
        """
        col = [(r[n - 1] if len(r) >= n else "") for r in self.rows]
        while col and not str(col[-1]).strip():
            col.pop()
        return col

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
        if rows:
            self.row_count = rows


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


# ── Column alignment (the production data-shift bug) ──────────────────────

class LegacyJunkSheet(FakeSheet):
    """A sheet shaped like the real one: a correct header, then legacy rows
    whose only populated cells sit in the MIDDLE columns. gspread's append_row
    infers the table's extent from that data and concludes the table starts at
    column H — so it writes every field seven columns right of where it belongs.
    """

    def __init__(self):
        rows = [list(tools.CSV_HEADERS)]
        for _ in range(40):
            junk = [""] * len(tools.CSV_HEADERS)
            for j in range(7, 12):
                junk[j] = "0"
            rows.append(junk)
        super().__init__(rows)


@pytest.fixture
def junk_sheet(monkeypatch):
    sheet = LegacyJunkSheet()
    monkeypatch.setattr(tools, "_get_sheet", lambda username=None: sheet)
    return sheet


def _written(sheet, session_id):
    return next((r for r in sheet.rows if r and r[0] == session_id), None)


def test_session_id_lands_in_column_a_despite_legacy_junk(junk_sheet):
    """In production this wrote the session id into the TabSwitches column."""
    tools._sync_sheet_now(_row("sess-align", "Alice"))
    row = _written(junk_sheet, "sess-align")
    assert row is not None, "row was not written into a column-A anchored position"
    assert row[0] == "sess-align"
    assert row[tools.CSV_HEADERS.index("Name")] == "Alice"


def test_every_field_matches_its_header_column(junk_sheet):
    r = tools._blank_row("sess-cols")
    tools._apply_answer(r, "What is a LEFT JOIN?", "It keeps all left rows.",
                        name="Bob", email="b@x.com", role="data_analytics")
    tools._sync_sheet_now(r)
    written = _written(junk_sheet, "sess-cols")
    H = tools.CSV_HEADERS
    assert written[H.index("Name")] == "Bob"
    assert written[H.index("Email")] == "b@x.com"
    assert written[H.index("Role")] == "data_analytics"
    assert written[H.index("Q1")] == "What is a LEFT JOIN?"
    # The column that used to receive the session id must hold its real value.
    assert written[H.index("TabSwitches")] == "0"


def test_repeat_saves_update_one_row_not_append_many(junk_sheet):
    """Production produced 15 rows for a single interview: the id was written
    to column H, so the column-A lookup never matched and each answer appended."""
    for i in range(1, 6):
        r = tools._blank_row("sess-one")
        for j in range(1, i + 1):
            tools._apply_answer(r, f"Q{j}", f"A{j}", name="Carol")
        tools._sync_sheet_now(r)
    matches = [r for r in junk_sheet.rows if r and r[0] == "sess-one"]
    assert len(matches) == 1, f"one interview produced {len(matches)} rows"
    assert matches[0][tools.CSV_HEADERS.index("QuestionsAnswered")] == "5"


def test_next_free_row_skips_the_header_and_ignores_junk(junk_sheet):
    # Column A holds only the header, so the first free row is 2 — the junk
    # rows below have nothing in column A and must not push the write down.
    assert tools._next_free_row(junk_sheet) == 2


def test_two_sessions_get_two_distinct_rows(junk_sheet):
    tools._sync_sheet_now(_row("sess-a", "A"))
    tools._sync_sheet_now(_row("sess-b", "B"))
    assert _written(junk_sheet, "sess-a")[1] == "A"
    assert _written(junk_sheet, "sess-b")[1] == "B"
    assert _written(junk_sheet, "sess-a") is not _written(junk_sheet, "sess-b")


def test_grid_is_grown_when_the_target_row_is_past_the_end(monkeypatch):
    sheet = FakeSheet([list(tools.CSV_HEADERS)])
    sheet.row_count = 1
    monkeypatch.setattr(tools, "_get_sheet", lambda username=None: sheet)
    tools._sync_sheet_now(_row("sess-grow"))
    assert _written(sheet, "sess-grow") is not None
