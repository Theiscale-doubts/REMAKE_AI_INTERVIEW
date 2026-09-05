import os
import csv
import json
import shutil
import threading
from datetime import datetime
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# One row per interview session (not per question). The candidate's identity,
# proctoring counters and final score live in fixed leading columns; every
# question/answer exchange is then flattened into its own pair of columns on
# that same row, so a reviewer opening the sheet sees one line per candidate.
#
# 20 pairs is deliberate headroom over agent.MAX_QUESTIONS (15) — the adaptive
# interview can never produce more than that, so no real session is ever
# truncated, and the spare columns cost nothing but a wider empty tail.
MAX_QA_PAIRS = 20

BASE_HEADERS = [
    "Session_id", "Name", "Email", "Role", "Score", "QuestionsAnswered",
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

_creds = None
try:
    credentials_json = os.getenv("google_credentials_json")
    if credentials_json:
        credentials_dict = json.loads(credentials_json)
        if "client_email" not in credentials_dict:
            print("WARNING: google_credentials_json is incomplete (missing client_email) — using CSV only.")
        else:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            _creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    else:
        print("WARNING: google_credentials_json not set — using CSV only.")
except Exception as e:
    print(f"WARNING: Failed to init Google Sheets credentials: {e}")


def _get_sheet(username="Interview"):
    client = gspread.authorize(_creds)
    return client.open(username).sheet1


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
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, "interview_log.csv")
    with _csv_lock:
        _archive_if_stale(csv_path)
        rows = _read_csv_rows(csv_path)
        target = next((r for r in rows if r.get("Session_id") == session_id), None)
        if target is None:
            target = _blank_row(session_id)
            rows.append(target)
        _apply_answer(target, question, answer, **meta)
        _write_csv_rows(csv_path, rows)
        return dict(target)


def _sheet_row_index(sheet, session_id: str) -> int | None:
    """1-based row number for a session, or None if it isn't on the sheet yet."""
    for idx, value in enumerate(sheet.col_values(1), start=1):
        if value == session_id:
            return idx
    return None


def _ensure_sheet_headers(sheet) -> None:
    existing = sheet.row_values(1)
    if not existing:
        sheet.append_row(CSV_HEADERS)
    elif existing != CSV_HEADERS:
        sheet.insert_row(CSV_HEADERS, 1)


def _sync_sheet(row: dict, username="Interview") -> str:
    """Mirror one session's row into Google Sheets, updating in place."""
    if _creds is None:
        return "Google Sheets not configured — skipped."
    try:
        sheet = _get_sheet(username)
        _ensure_sheet_headers(sheet)
        values = [row.get(h, "") for h in CSV_HEADERS]
        idx = _sheet_row_index(sheet, row.get("Session_id", ""))
        if idx is None:
            sheet.append_row(values)
        else:
            sheet.update(range_name=f"A{idx}", values=[values])
        return "data stored"
    except Exception as e:
        return f"Failed to Add values: {str(e)}"


def add_values(new_row, username="Interview"):
    """Append a raw row. Retained for backwards compatibility only — the
    per-session flow goes through save_qa_tool/record_score instead."""
    if _creds is None:
        return "Google Sheets not configured — skipped."
    try:
        sheet = _get_sheet(username)
        _ensure_sheet_headers(sheet)
        sheet.append_row([_sheet_safe(v) for v in new_row])
        return "data stored"
    except Exception as e:
        return f"Failed to Add values: {str(e)}"


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
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, "interview_log.csv")
    with _csv_lock:
        rows = _read_csv_rows(csv_path)
        target = next((r for r in rows if r.get("Session_id") == session_id), None)
        if target is None:
            return "session not found in log — score not recorded."
        target["Score"] = str(score)
        target["UpdatedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _write_csv_rows(csv_path, rows)
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


def _extract_from_csv(session_id_to_find=None):
    """Read interview data from the local CSV."""
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, "interview_log.csv")
    rows = _read_csv_rows(csv_path)
    if session_id_to_find is not None:
        rows = [r for r in rows if str(r.get("Session_id", "")) == str(session_id_to_find)]
    return json.dumps(_rows_to_qa_list(rows), indent=2)


def extract_values(session_id_to_find=None):
    """Read from Google Sheets; fall back to local CSV if unavailable or no match found."""
    if _creds is not None:
        try:
            sheet = _get_sheet("Interview")
            values = sheet.get_all_values()
            if values:
                headers = [h.strip() for h in values[0]]
                if "Session_id" in headers:
                    rows = [dict(zip(headers, v)) for v in values[1:]]
                    if session_id_to_find is not None:
                        rows = [r for r in rows
                                if str(r.get("Session_id", "")) == str(session_id_to_find)]
                    entries = _rows_to_qa_list(rows)
                    if entries:
                        return json.dumps(entries, indent=2)
        except Exception as e:
            print(f"Google Sheets read failed, falling back to CSV: {e}")

    return _extract_from_csv(session_id_to_find)
