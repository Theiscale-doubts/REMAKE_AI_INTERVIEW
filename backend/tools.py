import os
import csv
import shutil
from datetime import datetime
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

CSV_HEADERS = [
    "Question", "Answer", "Session_id", "Name", "Email", "Role",
    "TabSwitches", "FaceLostCount", "FaceLostSeconds", "MultipleFacesCount", "MovementEvents",
    "Timestamp",
]

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


def _ensure_sheet_headers(sheet):
    """Write header row to Google Sheet if it is empty."""
    existing = sheet.get_all_values()
    if not existing:
        sheet.append_row(CSV_HEADERS)
    elif existing[0] != CSV_HEADERS:
        # Sheet has data but wrong/missing headers — insert header row at top
        sheet.insert_row(CSV_HEADERS, 1)


def _ensure_csv_headers(csv_path):
    """Archive the CSV if it has old/wrong headers so a fresh one is created."""
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            first_row = next(reader)
        except StopIteration:
            return
    if first_row != CSV_HEADERS:
        bak = csv_path + ".bak"
        shutil.move(csv_path, bak)
        print(f"Archived old interview_log.csv → interview_log.csv.bak (header mismatch)")


def add_values(new_row, username="Interview"):
    if _creds is None:
        return "Google Sheets not configured — skipped."
    try:
        sheet = _get_sheet(username)
        _ensure_sheet_headers(sheet)
        sheet.append_row(new_row)
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
) -> str:
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, "interview_log.csv")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [
        question, answer, session_id, name, email, role,
        tab_switches or 0, face_lost_count or 0, face_lost_seconds or 0,
        multiple_faces_count or 0, movement_events or 0,
        current_time,
    ]

    os.makedirs(base_dir, exist_ok=True)
    _ensure_csv_headers(csv_path)

    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADERS)
        writer.writerow(row)

    return add_values(row, username="Interview")


def _extract_from_csv(session_id_to_find=None):
    """Read interview data from the local CSV."""
    base_dir = os.path.dirname(__file__)
    csv_path = os.path.join(base_dir, "interview_log.csv")
    if not os.path.exists(csv_path):
        return json.dumps([])
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if session_id_to_find is None:
        return json.dumps(rows, indent=2)
    filtered = [r for r in rows if str(r.get("Session_id", "")) == str(session_id_to_find)]
    return json.dumps(filtered, indent=2)


def extract_values(session_id_to_find=None):
    """Read from Google Sheets; fall back to local CSV if unavailable or no match found."""
    if _creds is not None:
        try:
            sheet = _get_sheet("Interview")
            rows = sheet.get_all_values()
            if rows:
                headers = [h.strip() for h in rows[0]]
                if "Session_id" in headers:
                    data = [dict(zip(headers, row)) for row in rows[1:]]
                    if session_id_to_find is None:
                        return json.dumps(data, indent=2)
                    filtered = [r for r in data if str(r.get("Session_id", "")) == str(session_id_to_find)]
                    if filtered:
                        return json.dumps(filtered, indent=2)
        except Exception as e:
            print(f"Google Sheets read failed, falling back to CSV: {e}")

    return _extract_from_csv(session_id_to_find)
