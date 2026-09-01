"""
Google Sheets client for reading/writing trip expenses.

AGENTIC AI CONCEPT: "Tool Integration"
───────────────────────────────────────
In agentic AI, "tools" are external systems the agent can interact with.
Our bot's toolbox so far:
  1. Gemini (LLM) — understands human language  (llm_parser.py)
  2. Google Sheets  — persistent data storage    (this file)
  3. LINE Messaging — communicates with the user (app.py)

This module wraps the Google Sheets API so the rest of our code can call
simple functions like `append_expense(...)` without worrying about OAuth,
cell ranges, or API quirks.

HOW GOOGLE SHEETS AUTH WORKS (for beginners):
─────────────────────────────────────────────
1. You create a "service account" in Google Cloud Console — think of it as
   a robot Google account that your code logs in as.
2. You download a JSON key file (like a password) for that robot account.
3. You share your Google Sheet with the robot's email address, giving it
   Editor access — just like sharing with a real person.
4. This code uses that JSON key file to authenticate, then reads/writes
   the sheet on the robot's behalf.
"""

import os
import logging
from datetime import datetime, timezone, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────

# Bangkok timezone (UTC+7) — we need this to decide "what day is it?"
# when determining whether to write a date or leave the cell blank.
BKK_TZ = timezone(timedelta(hours=7))

# Which columns map to which data (Right table: K, L, M, N, O):
#   K = รายการที่ (item number)
#   L = วันที่ (date)
#   M = รายการ (description)
#   N = จำนวนเงินที่จ่าย (amount)
#   O = สถานะ (status)
COL_ITEM_NUMBER = "K"
COL_DATE = "L"
COL_DESCRIPTION = "M"
COL_AMOUNT = "N"
COL_STATUS = "O"


# ── Sheets service setup ────────────────────────────────────────────────

_service = None


def _get_service():
    """
    Lazy-initialize the Google Sheets API service.

    'Lazy' means we don't create the connection when the file is imported —
    we wait until the first time someone actually calls a Sheets function.
    This avoids errors at startup if credentials aren't configured yet.
    """
    global _service
    if _service is not None:
        return _service

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    # 1. First check if credentials JSON string is passed via environment variable (ideal for cloud hosts)
    creds_json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if creds_json_str:
        import json
        info = json.loads(creds_json_str)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=scopes
        )
    else:
        # 2. Otherwise load from local key file (for local development)
        creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")
        if not os.path.exists(creds_file):
            raise RuntimeError(
                f"Google service account credentials not found.\n"
                f"Provide GOOGLE_SERVICE_ACCOUNT_JSON env var or place '{creds_file}' in project root."
            )
        credentials = service_account.Credentials.from_service_account_file(
            creds_file, scopes=scopes
        )

    _service = build("sheets", "v4", credentials=credentials)
    logger.info("Google Sheets service initialized successfully")
    return _service


def _get_sheet_id() -> str:
    """Get the Google Sheet ID from environment variables."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise RuntimeError(
            "Missing GOOGLE_SHEET_ID in .env — find it in your sheet's URL:\n"
            "https://docs.google.com/spreadsheets/d/THIS_PART/edit"
        )
    return sheet_id


def _get_tab_name() -> str:
    """
    Get the sheet tab name from environment (defaults to 'Sheet1').
    If your tab has a Thai name like 'แผ่น1', set GOOGLE_SHEET_TAB in .env.
    """
    return os.getenv("GOOGLE_SHEET_TAB", "Sheet1")


# ── Core functions ───────────────────────────────────────────────────────

def get_next_row() -> int:
    """
    Find the next empty row in the right table (columns K to O).

    HOW IT WORKS:
    Row 4 contains column headers.
    Rows 5+ contain expense items.
    We find the first row where Column M (Description) is empty.

    Returns the 1-based row number (e.g., 11 = next available row).
    """
    service = _get_service()
    sheet_id = _get_sheet_id()
    tab = _get_tab_name()

    # Read Column M (Description), rows 5 to 35
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{tab}!M5:M35")
        .execute()
    )
    rows = result.get("values", [])

    for i, row in enumerate(rows):
        if not row or not str(row[0]).strip():
            return i + 5  # +5 because range starts at row 5

    return len(rows) + 5


def should_write_date(target_row: int) -> bool:
    """
    Decide if we should write today's date or leave it blank.

    Checks Column L (Date) from row 5 up to target_row - 1.
    If the last non-empty date matches today, don't write date.
    """
    service = _get_service()
    sheet_id = _get_sheet_id()
    tab = _get_tab_name()

    if target_row <= 5:
        return True

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{tab}!L5:L{target_row - 1}")
        .execute()
    )
    date_cells = result.get("values", [])

    today_str = _today_str()
    for row in reversed(date_cells):
        if row and str(row[0]).strip():
            last_date = str(row[0]).strip()
            return last_date != today_str

    return True


def append_expense(description: str, amount: float) -> int:
    """
    Write a new expense to the next empty row in columns K, L, M, N, O.

    Steps:
    1. Find the next empty row (where Col M is blank)
    2. Decide if we need to write today's date in Col L
    3. Write Item # (Col K), Date (Col L), Description (Col M), Amount (Col N)
    4. Return the row number
    """
    service = _get_service()
    sheet_id = _get_sheet_id()
    tab = _get_tab_name()

    row_num = get_next_row()
    write_date = should_write_date(row_num)
    item_num = row_num - 4  # Row 5 is Item 1, Row 11 is Item 7, etc.

    logger.info(
        "Writing expense to row %d (Item #%d): %s ฿%.0f (date: %s)",
        row_num, item_num, description, amount, "yes" if write_date else "no"
    )

    date_value = _today_str() if write_date else ""

    data = [
        {
            "range": f"{tab}!{COL_ITEM_NUMBER}{row_num}",
            "values": [[item_num]],
        },
        {
            "range": f"{tab}!{COL_DATE}{row_num}",
            "values": [[date_value]],
        },
        {
            "range": f"{tab}!{COL_DESCRIPTION}{row_num}",
            "values": [[description]],
        },
        {
            "range": f"{tab}!{COL_AMOUNT}{row_num}",
            "values": [[amount]],
        },
    ]

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=sheet_id,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()

    logger.info("Successfully wrote expense to row %d", row_num)
    return row_num


def update_status(row_number: int, status: str) -> None:
    """
    Update the สถานะ (status) column for a specific row and color the cell:
      - "จ่ายแล้ว": Green background
      - "รอดำเนินการ": Gray background
    """
    service = _get_service()
    sheet_id = _get_sheet_id()
    tab = _get_tab_name()

    # 1. Update the cell text value
    cell_range = f"{tab}!{COL_STATUS}{row_number}"
    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=cell_range,
        valueInputOption="USER_ENTERED",
        body={"values": [[status]]},
    ).execute()

    # 2. Update cell background color
    try:
        tab_gid = _get_tab_gid(service, sheet_id, tab)
        # Column O is column index 14 (0-based)
        col_index = ord(COL_STATUS.upper()) - ord("A")
        
        if "จ่าย" in status:
            # Light green (#d9ead3)
            bg_color = {"red": 0.85, "green": 0.93, "blue": 0.83}
        else:
            # Light gray (#efefef)
            bg_color = {"red": 0.94, "green": 0.94, "blue": 0.94}

        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": tab_gid,
                        "startRowIndex": row_number - 1,
                        "endRowIndex": row_number,
                        "startColumnIndex": col_index,
                        "endColumnIndex": col_index + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": bg_color
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests},
        ).execute()
    except Exception as e:
        logger.warning("Could not apply background color to row %d: %s", row_number, e)

    logger.info("Updated row %d status to '%s' with color", row_number, status)


# ── Helpers ───────────────────────────────────────────────────────────────

_tab_gids: dict[str, int] = {}

def _get_tab_gid(service, sheet_id: str, tab_name: str) -> int:
    """Get the numeric sheetId (gid) for a given tab name."""
    global _tab_gids
    if tab_name in _tab_gids:
        return _tab_gids[tab_name]

    metadata = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    for s in metadata.get("sheets", []):
        props = s.get("properties", {})
        _tab_gids[props.get("title")] = props.get("sheetId", 0)

    return _tab_gids.get(tab_name, 0)


def _today_str() -> str:
    """
    Get today's date in DD/MM/YYYY format (Thai convention).

    Uses Bangkok timezone (UTC+7) so that a message sent at 11pm Bangkok
    time doesn't accidentally get logged as the next day (which it would be
    in UTC).
    """
    now = datetime.now(BKK_TZ)
    return now.strftime("%d/%m/%Y")

