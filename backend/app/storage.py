import os
import csv
import json
import time
import shutil
import threading
from datetime import datetime
from dotenv import load_dotenv

# backend/ — one level up from this module (app/).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# All runtime data lives together. The CSV previously anchored on the backend
# directory while the JSON stores honoured DATA_DIR, so pointing DATA_DIR at a
# mounted disk moved half the data and left the CSV on ephemeral storage.
DATA_DIR = os.getenv("DATA_DIR", _BACKEND_DIR)


def _csv_file() -> str:
    return os.path.join(DATA_DIR, "interview_log.csv")
import gspread
from google.oauth2.service_account import Credentials

# VOXHIRE_SKIP_DOTENV keeps a test run from picking up the developer's local
# credentials — without it, a test that exercises the sync path writes into the
# real production spreadsheet.
if not os.getenv("VOXHIRE_SKIP_DOTENV"):
    load_dotenv(os.path.join(_BACKEND_DIR, ".env"))

# One row per interview session (not per question). The candidate's identity,
# proctoring counters and final score live in fixed leading columns; every
# question/answer exchange is then flattened into its own pair of columns on
# that same row, so a reviewer opening the sheet sees one line per candidate.
#
# 20 pairs is deliberate headroom over agent.MAX_QUESTIONS (15) — the adaptive
# interview can never produce more than that, so no real session is ever
# truncated, and the spare columns cost nothing but a wider empty tail.
MAX_QA_PAIRS = 20

# "AllQuestions" is a reviewer convenience: every question the interview asked,
# numbered, in one cell. The Q1..Q20 columns already hold the same text, but
# reading an interview out of them means scrolling across 40 columns — this
# column makes a session's line of questioning readable at a glance, and makes
# the sheet searchable by question text with a single Ctrl-F over one column.
BASE_HEADERS = [
    "Session_id", "Name", "Email", "Role", "Score", "QuestionsAnswered",
    "AllQuestions",
    "TabSwitches", "FaceLostCount", "FaceLostSeconds", "MultipleFacesCount",
    "MovementEvents", "StartedAt", "UpdatedAt", "Photo",
]


def _qa_headers(pairs: int = MAX_QA_PAIRS) -> list:
    return [h for i in range(1, pairs + 1) for h in (f"Q{i}", f"A{i}")]


CSV_HEADERS = BASE_HEADERS + _qa_headers()

# The CSV is now read-modify-write (a row is updated in place as each answer
# arrives) rather than append-only, so concurrent /api/save calls from two
# candidates interviewing at once would otherwise interleave and lose a row.
_csv_lock = threading.Lock()

# Google auth. oauth2client — which this used to import — was deprecated by
# Google in 2017 and its repo is archived; it survives here only as a
# transitive leftover. google-auth is the supported library, is already pulled
# in by gspread, and is what gspread's own docs use.
_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_creds = None
try:
    credentials_json = os.getenv("google_credentials_json")
    if credentials_json:
        credentials_dict = json.loads(credentials_json)
        missing = [k for k in ("client_email", "private_key", "token_uri") if k not in credentials_dict]
        if missing:
            print(f"WARNING: google_credentials_json is incomplete (missing {', '.join(missing)}) — using CSV only.")
        else:
            _creds = Credentials.from_service_account_info(credentials_dict, scopes=_SHEETS_SCOPES)
    else:
        print("WARNING: google_credentials_json not set — using CSV only.")
except Exception as e:
    print(f"WARNING: Failed to init Google Sheets credentials: {e}")


SHEET_NAME = os.getenv("SHEET_NAME", "Interview")


def _get_sheet(username=None):
    client = gspread.authorize(_creds)
    return client.open(username or SHEET_NAME).sheet1


# ── Durability self-check ─────────────────────────────────────────────────
# On a host with an ephemeral filesystem (Render's free tier) Google Sheets is
# the ONLY copy of an interview that survives a deploy or a cold start. Writes
# to it are best-effort by design, so a wrong credential, a renamed sheet or an
# unshared spreadsheet used to fail silently: every interview looked fine and
# was permanently lost on the next restart. This makes that state observable.
_sheets_status: dict = {
    "configured": _creds is not None,
    "reachable": None,          # None = not yet checked
    "detail": "not checked yet",
    "checked_at": None,
    "spreadsheet": SHEET_NAME,
}


def sheets_status() -> dict:
    return dict(_sheets_status)


def verify_sheets(username: str | None = None) -> dict:
    """Open the spreadsheet once and record whether it actually worked.

    Called at startup and surfaced via /api/healthz. Cheap (one API call) and
    it fails loudly instead of at the moment the data is needed.
    """
    name = username or _sheets_status["spreadsheet"]
    _sheets_status["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if _creds is None:
        _sheets_status.update(
            configured=False,
            reachable=False,
            detail="google_credentials_json is not set — interviews are stored ONLY on local disk, "
                   "which is wiped on every deploy and cold start on an ephemeral host.",
        )
        print(f"CRITICAL: {_sheets_status['detail']}")
        return sheets_status()

    try:
        sheet = _get_sheet(name)
        _ensure_sheet_headers(sheet)
        _sheets_status.update(
            configured=True, reachable=True,
            detail=f"connected to '{name}' ({sheet.row_count} rows)",
        )
        print(f"Google Sheets OK: {_sheets_status['detail']}")
    except gspread.SpreadsheetNotFound:
        _sheets_status.update(
            configured=True, reachable=False,
            detail=f"spreadsheet '{name}' not found — check the name, and that it is shared with "
                   f"the service account ({_service_account_email() or 'unknown'}) as an Editor.",
        )
        print(f"CRITICAL: Google Sheets unreachable — {_sheets_status['detail']}")
    except Exception as exc:
        _sheets_status.update(
            configured=True, reachable=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
        print(f"CRITICAL: Google Sheets unreachable — {_sheets_status['detail']}")
    return sheets_status()


def _service_account_email() -> str | None:
    """The address the spreadsheet must be shared with — the single most common
    setup mistake, so name it directly in the error rather than making the
    operator go digging in the credentials JSON."""
    return getattr(_creds, "service_account_email", None)


def _sheet_safe(value):
    """Guard against CSV/Sheets formula injection (OWASP-documented): a cell
    value starting with =, +, -, @, tab, or CR can be interpreted as a
    formula by Excel/Google Sheets when the file is opened. A candidate's
    transcribed answer is untrusted input that ends up in exactly that
    position, so prefix it with a single quote — the same trick spreadsheet
    apps themselves use to force literal-text interpretation.
    """
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _blank_row(session_id: str) -> dict:
    row = {h: "" for h in CSV_HEADERS}
    row["Session_id"] = session_id or ""
    row["QuestionsAnswered"] = "0"
    row["StartedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for key in ("TabSwitches", "FaceLostCount", "FaceLostSeconds",
                "MultipleFacesCount", "MovementEvents"):
        row[key] = "0"
    return row


def _build_all_questions(row: dict) -> str:
    """Numbered list of every question stored on this row, newest included.

    Rebuilt from the Q1..Qn columns each time rather than appended to, so it
    always reflects what is actually stored and can never drift out of sync
    with them (e.g. if a row is edited by hand or replayed).
    """
    parts = []
    for i in range(1, MAX_QA_PAIRS + 1):
        q = (row.get(f"Q{i}") or "").strip()
        if not q:
            continue
        # Q cells were passed through _sheet_safe on write, which may have
        # prefixed a quote to neutralise formula injection; strip it for display.
        parts.append(f"{i}. {q[1:] if q.startswith(chr(39)) else q}")
    joined = "\n".join(parts)
    # Google Sheets caps a cell at 50,000 characters; stay well under it.
    return _sheet_safe(joined[:45_000])


def _apply_answer(row: dict, question: str, answer: str, **meta) -> dict:
    """Fold one Q/A exchange plus the latest metadata into a session's row."""
    try:
        answered = int(float(row.get("QuestionsAnswered") or 0))
    except (TypeError, ValueError):
        answered = 0

    slot = answered + 1
    if slot <= MAX_QA_PAIRS:
        row[f"Q{slot}"] = _sheet_safe(question or "")
        row[f"A{slot}"] = _sheet_safe(answer or "")
        row["QuestionsAnswered"] = str(slot)
        row["AllQuestions"] = _build_all_questions(row)
    else:
        # Unreachable for real interviews (capped at 15 questions); log rather
        # than silently dropping the answer if the cap is ever raised.
        print(f"WARNING: session {row.get('Session_id')} exceeded {MAX_QA_PAIRS} Q/A pairs — answer not stored in sheet.")

    # Identity fields: fill in, but never blank out a value already recorded.
    for key, value in (("Name", meta.get("name")), ("Email", meta.get("email")),
                       ("Role", meta.get("role"))):
        if value:
            row[key] = _sheet_safe(value)

    # Proctoring counters are cumulative on the frontend, so keep the highest
    # value ever reported rather than whatever the last call happened to send.
    for key, value in (("TabSwitches", meta.get("tab_switches")),
                       ("FaceLostCount", meta.get("face_lost_count")),
                       ("FaceLostSeconds", meta.get("face_lost_seconds")),
                       ("MultipleFacesCount", meta.get("multiple_faces_count")),
                       ("MovementEvents", meta.get("movement_events"))):
        try:
            incoming = int(float(value or 0))
            current = int(float(row.get(key) or 0))
        except (TypeError, ValueError):
            continue
        row[key] = str(max(incoming, current))

    # The snapshot is captured once; never overwrite one already stored.
    if meta.get("photo") and not row.get("Photo"):
        row["Photo"] = meta["photo"]

    row["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return row


def _archive_if_stale(csv_path: str) -> None:
    """Archive a CSV written under the old one-row-per-question layout.

    The backup name carries a timestamp so this never clobbers an existing
    interview_log.csv.bak from a previous migration.
    """
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        try:
            first_row = next(csv.reader(f))
        except StopIteration:
            return
    if first_row != CSV_HEADERS:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{csv_path}.{stamp}.bak"
        shutil.move(csv_path, bak)
        print(f"Archived previous interview_log.csv → {os.path.basename(bak)} (layout changed)")


def _read_csv_rows(csv_path: str) -> list:
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv_rows(csv_path: str, rows: list) -> None:
    """Write atomically — a crash mid-write would otherwise leave the log
    truncated, and unlike the old append-only file every row is at stake."""
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in CSV_HEADERS})
    os.replace(tmp, csv_path)


def _upsert_csv(session_id: str, question: str, answer: str, **meta) -> dict:
    path = _csv_file()
    with _csv_lock:
        _archive_if_stale(path)
        rows = _read_csv_rows(path)
        target = next((r for r in rows if r.get("Session_id") == session_id), None)
        if target is None:
            target = _blank_row(session_id)
            rows.append(target)
        _apply_answer(target, question, answer, **meta)
        _write_csv_rows(path, rows)
        return dict(target)


def _sheet_row_index(sheet, session_id: str) -> int | None:
    """1-based row number for a session, or None if it isn't on the sheet yet.

    Returns None for a blank session id. Without that guard the loop below
    matched the first EMPTY cell in column A — so a save carrying no session id
    resolved to some unrelated row and _sync_sheet_now overwrote it with a
    blank record. Sheets with gaps in column A (any sheet that has had rows
    deleted) were silently corrupted one row at a time.
    """
    target = (session_id or "").strip()
    if not target:
        return None
    for idx, value in enumerate(sheet.col_values(1), start=1):
        if (value or "").strip() == target:
            return idx
    return None


def _next_free_row(sheet) -> int:
    """First row with no session id in column A.

    Deliberately NOT sheet.append_row(). gspread's append infers the table's
    extent from whatever data the sheet already contains, and a sheet carrying
    legacy rows whose only populated cells sit in the middle columns (H-L, say,
    from an older schema) makes it conclude the table STARTS at column H. It
    then appends there, writing every field seven columns to the right of where
    the header says it belongs — silently, and reporting success.

    That is exactly what happened in production: session ids landed under
    TabSwitches, so _sheet_row_index (which reads column A) never found an
    existing session and every single answer appended a brand-new row.

    Anchoring on column A instead makes the position explicit and immune to
    whatever junk the rest of the sheet holds.
    """
    column_a = sheet.col_values(1)
    return len(column_a) + 1


def _write_row(sheet, idx: int, values: list) -> None:
    """Write one full session row at `idx`, anchored at column A."""
    # Grow the grid if the target row is past the end, otherwise the API
    # rejects the range.
    if idx > sheet.row_count:
        sheet.resize(rows=idx + 50)
    if sheet.col_count < len(CSV_HEADERS):
        sheet.resize(cols=len(CSV_HEADERS))
    sheet.update(range_name=f"A{idx}", values=[values])


def _ensure_sheet_headers(sheet) -> None:
    """Make row 1 match CSV_HEADERS.

    A mismatch means the schema changed (a column was added, e.g.
    AllQuestions). The previous behaviour INSERTED a second header row above
    the old one, which left the sheet with two header rows and every existing
    record still sitting under the old layout. Updating row 1 in place keeps a
    single header; pre-existing rows simply have the new column empty, which is
    exactly right — those interviews ran before the column existed.
    """
    existing = sheet.row_values(1)
    if not existing:
        # Anchored write, not append_row — same table-inference hazard.
        sheet.update(range_name="A1", values=[CSV_HEADERS])
        return
    if existing == CSV_HEADERS:
        return
    # Widen the sheet first if the new schema has more columns than the grid.
    if sheet.col_count < len(CSV_HEADERS):
        sheet.resize(cols=len(CSV_HEADERS))
    sheet.update(range_name="A1", values=[CSV_HEADERS])
    print(f"Sheet header updated to current schema ({len(CSV_HEADERS)} columns).")


def _sync_sheet_now(row: dict, username="Interview") -> str:
    """Mirror one session's row into Google Sheets, updating in place.

    Synchronous and single-attempt. Callers on the request path should use
    _sync_sheet (which queues) rather than this, so a slow or failing Sheets
    API never blocks a candidate mid-interview.
    """
    if _creds is None:
        return "Google Sheets not configured — skipped."
    # A row with no session id has no identity: it can never be found again,
    # can never be updated, and (before the guard in _sheet_row_index) could
    # overwrite an unrelated row. Refuse it outright.
    if not (row.get("Session_id") or "").strip():
        return "Failed to Add values: row has no Session_id"
    try:
        sheet = _get_sheet(username)
        _ensure_sheet_headers(sheet)
        values = [row.get(h, "") for h in CSV_HEADERS]
        idx = _sheet_row_index(sheet, row.get("Session_id", ""))
        if idx is None:
            idx = _next_free_row(sheet)
        _write_row(sheet, idx, values)
        _sheets_status.update(reachable=True, detail="last write succeeded")
        return "data stored"
    except Exception as e:
        # A sheet that was healthy at boot can break later (quota, revoked
        # share, renamed file). Record it so /api/healthz reflects reality
        # rather than a stale startup result.
        _sheets_status.update(reachable=False, detail=f"last write failed: {type(e).__name__}: {e}")
        print(f"WARNING: Google Sheets write failed — {e}")
        return f"Failed to Add values: {str(e)}"


def _sync_sheet(row: dict, username="Interview") -> str:
    """Queue this session's row for the durable sheet and return immediately.

    Deliberately off the request path: a Sheets call is 300-800ms on a good day
    and can hang on a bad one, and the candidate is waiting for their next
    question. The local CSV write has already happened synchronously, so the
    data exists either way; this only governs when it reaches the sheet.
    """
    if _creds is None:
        return "Google Sheets not configured — skipped."
    _enqueue_sync(dict(row))
    return "queued"


# ── Write-behind sync queue ───────────────────────────────────────────────
# Sheets is the system of record, but a write to it can fail transiently
# (quota, a blip, a cold DNS lookup). Previously a failed write was logged and
# the row was simply gone from the durable copy — the local CSV still had it,
# but nothing ever retried, so the "system of record" quietly drifted out of
# sync with reality and nobody found out until they opened the sheet.
#
# Writes are now queued and retried in the background. Two properties make this
# safe and cheap:
#   * _sync_sheet writes the session's ENTIRE row (an upsert, not an append),
#     so a retry is idempotent and a newer row fully supersedes an older one.
#   * Because of that, pending writes are COALESCED per session — a candidate
#     answering ten questions while Sheets is down leaves one pending write,
#     not ten, and it carries the latest state.
_pending_writes: dict = {}          # session_id -> {"row": ..., "attempts": n, "next_try": ts}
_pending_lock = threading.Lock()
_pending_wake = threading.Event()
_worker_started = False
_worker_lock = threading.Lock()

SYNC_MAX_ATTEMPTS = int(os.getenv("SHEET_SYNC_MAX_ATTEMPTS", "6"))
SYNC_BASE_BACKOFF = float(os.getenv("SHEET_SYNC_BASE_BACKOFF", "5"))
SYNC_MAX_PENDING = int(os.getenv("SHEET_SYNC_MAX_PENDING", "500"))


def _dead_letter_path() -> str:
    return os.path.join(DATA_DIR, "sheet_dead_letter.jsonl")


def _to_dead_letter(row: dict, reason: str) -> None:
    """Last resort: a row that exhausted its retries is appended to a file so it
    can be replayed by hand. Losing it silently is the one outcome not allowed."""
    try:
        with open(_dead_letter_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": datetime.now().isoformat(), "reason": reason, "row": row}) + "\n")
        print(f"CRITICAL: sheet write permanently failed for session "
              f"{row.get('Session_id')} — parked in {os.path.basename(_dead_letter_path())} ({reason})")
    except Exception as exc:
        print(f"CRITICAL: could not even dead-letter the row: {exc}")


def _sync_worker() -> None:
    while True:
        # Sleep until the earliest scheduled retry rather than on a fixed tick.
        # A fixed poll interval silently becomes the floor on every retry delay,
        # so a 50ms backoff would really be a 5s one.
        with _pending_lock:
            due_times = [item["next_try"] for item in _pending_writes.values()]
        if due_times:
            wait_for = max(0.0, min(due_times) - time.time())
        else:
            wait_for = 30.0    # nothing queued; wake only to stay responsive
        _pending_wake.wait(timeout=min(wait_for, 30.0))
        _pending_wake.clear()
        now = time.time()
        with _pending_lock:
            due = [(sid, item) for sid, item in _pending_writes.items() if item["next_try"] <= now]
        for session_id, item in due:
            result = _sync_sheet_now(item["row"])
            with _pending_lock:
                current = _pending_writes.get(session_id)
                if current is None or current["row"] is not item["row"]:
                    # A newer row arrived while we were writing; leave it queued.
                    continue
                if result.startswith("data stored"):
                    _pending_writes.pop(session_id, None)
                    continue
                current["attempts"] += 1
                if current["attempts"] >= SYNC_MAX_ATTEMPTS:
                    _pending_writes.pop(session_id, None)
                    _to_dead_letter(current["row"], result)
                else:
                    # Exponential backoff, capped, so a long Sheets outage does
                    # not turn into a hot retry loop against the API.
                    delay = min(SYNC_BASE_BACKOFF * 2 ** (current["attempts"] - 1), 300)
                    current["next_try"] = time.time() + delay


def _ensure_worker() -> None:
    """Start the background syncer on first use (not at import), so importing
    this module in a test or a script never spawns a thread."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        threading.Thread(target=_sync_worker, name="sheet-sync", daemon=True).start()
        _worker_started = True


def _enqueue_sync(row: dict) -> None:
    session_id = row.get("Session_id") or ""
    with _pending_lock:
        if len(_pending_writes) >= SYNC_MAX_PENDING and session_id not in _pending_writes:
            _to_dead_letter(row, "pending queue full")
            return
        _pending_writes[session_id] = {"row": row, "attempts": 0, "next_try": 0.0}
    _ensure_worker()
    _pending_wake.set()


def sync_queue_depth() -> int:
    with _pending_lock:
        return len(_pending_writes)


def flush_sync_queue(timeout: float = 10.0) -> int:
    """Drain pending writes, best effort. Called on shutdown so an orderly
    restart does not strand rows that were one retry away from landing."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _pending_lock:
            pending = [(sid, item["row"]) for sid, item in _pending_writes.items()]
        if not pending:
            break
        for session_id, row in pending:
            if _sync_sheet_now(row).startswith("data stored"):
                with _pending_lock:
                    _pending_writes.pop(session_id, None)
    remaining = sync_queue_depth()
    if remaining:
        with _pending_lock:
            for item in _pending_writes.values():
                _to_dead_letter(item["row"], "not flushed before shutdown")
            _pending_writes.clear()
    return remaining


def save_qa_tool(
    question: str,
    answer: str,
    session_id: str | None = None,
    name: str | None = None,
    email: str | None = None,
    role: str | None = None,
    tab_switches: int | None = None,
    face_lost_count: int | None = None,
    face_lost_seconds: int | None = None,
    multiple_faces_count: int | None = None,
    movement_events: int | None = None,
    photo: str | None = None,
) -> str:
    """Record one Q/A exchange onto this session's single row."""
    row = _upsert_csv(
        session_id or "", question, answer,
        name=name, email=email, role=role,
        tab_switches=tab_switches, face_lost_count=face_lost_count,
        face_lost_seconds=face_lost_seconds,
        multiple_faces_count=multiple_faces_count,
        movement_events=movement_events, photo=photo,
    )
    return _sync_sheet(row)


def record_score(session_id: str, score) -> str:
    """Write the final score onto the session's existing row.

    The score only exists once the interview is over and the evaluation has
    run, so it is filled in after the fact rather than at answer time.
    """
    path = _csv_file()
    with _csv_lock:
        rows = _read_csv_rows(path)
        target = next((r for r in rows if r.get("Session_id") == session_id), None)
        if target is None:
            return "session not found in log — score not recorded."
        target["Score"] = str(score)
        target["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _write_csv_rows(path, rows)
        row = dict(target)
    return _sync_sheet(row)


def _row_to_qa_list(row: dict) -> list:
    """Expand one flattened session row back into the per-exchange dicts the
    evaluation endpoint consumes, so the wide layout stays an export format
    and callers upstream need no changes."""
    try:
        answered = int(float(row.get("QuestionsAnswered") or 0))
    except (TypeError, ValueError):
        answered = 0
    answered = min(answered, MAX_QA_PAIRS)

    shared = {k: row.get(k, "") for k in (
        "Session_id", "Name", "Email", "Role", "TabSwitches", "FaceLostCount",
        "FaceLostSeconds", "MultipleFacesCount", "MovementEvents",
    )}

    entries = []
    for i in range(1, answered + 1):
        question, answer = row.get(f"Q{i}", ""), row.get(f"A{i}", "")
        if not question and not answer:
            continue
        entry = dict(shared)
        entry["Question"] = question
        entry["Answer"] = answer
        # The report reads the snapshot off the first entry only.
        entry["Photo"] = row.get("Photo", "") if not entries else ""
        entries.append(entry)
    return entries


def _rows_to_qa_list(rows: list) -> list:
    out = []
    for row in rows:
        out.extend(_row_to_qa_list(row))
    return out


# ── Cached sheet reads ────────────────────────────────────────────────────
# Every read used to be a full sheet.get_all_values() round trip, so opening a
# result cost a whole-spreadsheet fetch. With a searchable results list that
# would be one fetch per keystroke, which both feels slow and burns the read
# quota (~300/min per project). One short-lived cache serves all readers.
_rows_cache: dict = {"rows": None, "fetched_at": 0.0, "source": "none"}
_rows_cache_lock = threading.Lock()
SHEET_CACHE_TTL = float(os.getenv("SHEET_CACHE_TTL_SECONDS", "45"))


# Header labels from this schema and from every earlier one. Older versions of
# _ensure_sheet_headers INSERTED a new header row above the old one instead of
# updating it, so real spreadsheets carry leftover header rows sitting in the
# data region. They must never be read back as interviews — without this guard
# they surface in the results list as sessions named "Answer".
_LEGACY_HEADER_TOKENS = {"Question", "Answer", "Timestamp", "Session_id ", "Name ", "Email ", "Role "}
_HEADER_TOKENS = {h.strip() for h in CSV_HEADERS} | {t.strip() for t in _LEGACY_HEADER_TOKENS}


def _is_interview_row(values: list) -> bool:
    """True only for a row that is real interview data.

    A row whose first cell is itself a column name is a stray header, not a
    session — no interview has a session id of "Question".
    """
    if not values:
        return False
    first = (values[0] or "").strip()
    return bool(first) and first not in _HEADER_TOKENS


def _rows_from_sheet() -> list | None:
    """All data rows as dicts, or None when Sheets is unusable."""
    if _creds is None:
        return None
    try:
        sheet = _get_sheet(_sheets_status["spreadsheet"])
        values = sheet.get_all_values()
        if not values:
            return []
        headers = [h.strip() for h in values[0]]
        if "Session_id" not in headers:
            return None
        _sheets_status.update(reachable=True, detail="last read succeeded")
        return [dict(zip(headers, v)) for v in values[1:] if _is_interview_row(v)]
    except Exception as exc:
        _sheets_status.update(reachable=False, detail=f"last read failed: {type(exc).__name__}: {exc}")
        print(f"WARNING: Google Sheets read failed, falling back to CSV: {exc}")
        return None


def get_all_rows(force: bool = False) -> list:
    """Every session row, from Sheets when possible and the local CSV otherwise.

    TTL-cached. `force` bypasses the cache — used when a caller needs a row it
    did not find, so a just-finished interview is never hidden behind the TTL.
    """
    now = time.time()
    with _rows_cache_lock:
        fresh = _rows_cache["rows"] is not None and (now - _rows_cache["fetched_at"]) < SHEET_CACHE_TTL
        if fresh and not force:
            return _rows_cache["rows"]

    rows = _rows_from_sheet()
    source = "sheets"
    if rows is None:
        rows = [
            r for r in _read_csv_rows(_csv_file())
            if _is_interview_row([r.get("Session_id", "")])
        ]
        source = "csv"

    with _rows_cache_lock:
        _rows_cache.update(rows=rows, fetched_at=time.time(), source=source)
    return rows


def invalidate_rows_cache() -> None:
    with _rows_cache_lock:
        _rows_cache.update(rows=None, fetched_at=0.0)


def _to_float(value, default=None):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(float(str(value).strip() or 0))
    except (TypeError, ValueError):
        return default


def session_summary(row: dict) -> dict:
    """One interview reduced to what a results list needs — never the photo or
    the full transcript, which would make the payload enormous for no reason."""
    return {
        "session_id": (row.get("Session_id") or "").strip(),
        "name": (row.get("Name") or "").strip(),
        "email": (row.get("Email") or "").strip(),
        "role": (row.get("Role") or "").strip(),
        "score": _to_float(row.get("Score")),
        "questions_answered": _to_int(row.get("QuestionsAnswered")),
        "started_at": (row.get("StartedAt") or "").strip(),
        "updated_at": (row.get("UpdatedAt") or "").strip(),
        "has_photo": bool((row.get("Photo") or "").strip()),
    }


def search_sessions(query: str = "", limit: int = 50, offset: int = 0, force: bool = False) -> dict:
    """Search completed interviews by name, email, role, session id or question text.

    Exists because results were previously reachable only by walking back from
    an invite record — delete the code (or lose the store on a restart) and a
    perfectly intact interview became unreachable. The durable sheet always has
    it; this makes it findable.
    """
    rows = get_all_rows(force=force)
    needle = (query or "").strip().lower()

    matched = []
    for row in rows:
        # Defence in depth: the same guard runs at read time, but applying it
        # here too means no row source can leak a stray header into the list.
        if not _is_interview_row([row.get("Session_id", "")]):
            continue
        if needle:
            haystack = " ".join(str(row.get(f, "") or "") for f in
                                ("Session_id", "Name", "Email", "Role", "AllQuestions"))
            if needle not in haystack.lower():
                continue
        matched.append(session_summary(row))

    # Most recent first. Rows written before UpdatedAt existed sort last rather
    # than crashing the comparison.
    matched.sort(key=lambda r: (r["updated_at"] or r["started_at"] or ""), reverse=True)

    with _rows_cache_lock:
        source = _rows_cache["source"]
    return {
        "results": matched[offset:offset + limit],
        "total": len(matched),
        "offset": offset,
        "limit": limit,
        "source": source,
        "durable": source == "sheets",
    }


def _extract_from_csv(session_id_to_find=None):
    """Read interview data from the local CSV."""
    rows = _read_csv_rows(_csv_file())
    if session_id_to_find is not None:
        rows = [r for r in rows if str(r.get("Session_id", "")) == str(session_id_to_find)]
    return json.dumps(_rows_to_qa_list(rows), indent=2)


def extract_values(session_id_to_find=None):
    """Read interview rows, preferring Sheets and falling back to the local CSV.

    Goes through the shared cache rather than fetching the whole spreadsheet on
    every call. A miss retries uncached before giving up, so an interview that
    finished seconds ago is never hidden behind the TTL.
    """
    for force in (False, True):
        rows = get_all_rows(force=force)
        if session_id_to_find is not None:
            rows = [r for r in rows
                    if str(r.get("Session_id", "")).strip() == str(session_id_to_find).strip()]
        entries = _rows_to_qa_list(rows)
        if entries:
            return json.dumps(entries, indent=2)
        if session_id_to_find is None:
            break

    # Nothing in the durable store — the local CSV may still have it (e.g. the
    # sheet write is queued but has not landed yet).
    return _extract_from_csv(session_id_to_find)
