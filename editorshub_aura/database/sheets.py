import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import GOOGLE_CREDENTIALS, GOOGLE_CREDENTIALS_FILE, GOOGLE_SHEET_KEY
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# ── Singleton connection pool ─────────────────────────────────────────────────
_gc: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None
_sheets_cache: dict[str, gspread.Worksheet] = {}


def _reset_connection():
    global _gc, _spreadsheet, _sheets_cache
    _gc = None
    _spreadsheet = None
    _sheets_cache = {}


def get_client() -> gspread.Client | None:
    global _gc
    if _gc is not None:
        return _gc
    try:
        if GOOGLE_CREDENTIALS:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        _gc = gspread.authorize(creds)
        logger.info("Google Sheets client authenticated.")
    except Exception as e:
        logger.error(f"Failed to authenticate Google Sheets: {e}")
        _gc = None
    return _gc


def _get_spreadsheet() -> gspread.Spreadsheet | None:
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet
    client = get_client()
    if not client or not GOOGLE_SHEET_KEY:
        return None
    try:
        _spreadsheet = client.open_by_key(GOOGLE_SHEET_KEY)
    except Exception as e:
        logger.error(f"Failed to open spreadsheet: {e}")
        _reset_connection()
    return _spreadsheet


def get_sheet(sheet_name: str) -> gspread.Worksheet | None:
    if sheet_name in _sheets_cache:
        return _sheets_cache[sheet_name]
    spreadsheet = _get_spreadsheet()
    if not spreadsheet:
        return None
    try:
        sheet = spreadsheet.worksheet(sheet_name)
        _sheets_cache[sheet_name] = sheet
        return sheet
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"Worksheet '{sheet_name}' not found.")
        return None
    except Exception as e:
        logger.error(f"Failed to open sheet '{sheet_name}': {e}")
        _reset_connection()
        return None


def _with_retry(fn):
    """Retry once after resetting the connection on any gspread error."""
    try:
        return fn()
    except Exception as e:
        logger.warning(f"Sheets op failed ({e}), retrying after reconnect…")
        _reset_connection()
        return fn()


def add_row(sheet_name: str, row_data: list):
    def _do():
        sheet = get_sheet(sheet_name)
        if not sheet:
            raise RuntimeError(f"Could not open sheet '{sheet_name}'.")
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        logger.info(f"Row added to '{sheet_name}'.")

    _with_retry(_do)


def get_all_records(sheet_name: str) -> list:
    def _do():
        sheet = get_sheet(sheet_name)
        return sheet.get_all_records() if sheet else []

    try:
        return _with_retry(_do)
    except Exception as e:
        logger.error(f"Failed to get records from '{sheet_name}': {e}")
        return []


def find_row_by_id(sheet_name: str, id_col_name: str, id_value):
    records = get_all_records(sheet_name)
    for index, record in enumerate(records, start=2):
        if str(record.get(id_col_name)) == str(id_value):
            return record, index
    return None, None


def update_cell(sheet_name: str, row_index: int, col_name: str, value):
    def _do():
        sheet = get_sheet(sheet_name)
        if not sheet:
            return
        header = sheet.row_values(1)
        if col_name in header:
            col_index = header.index(col_name) + 1
            sheet.update_cell(row_index, col_index, value)
        else:
            logger.warning(f"Column '{col_name}' not found in '{sheet_name}'.")

    try:
        _with_retry(_do)
    except Exception as e:
        logger.error(f"Failed to update cell in '{sheet_name}' row {row_index} col '{col_name}': {e}")


def get_latest_order_id() -> str:
    records = get_all_records("Orders")
    if not records:
        return "EH-000"
    return records[-1].get("OrderID", "EH-000")


def increment_order_id(last_id: str) -> str:
    try:
        num = int(last_id.split("-")[1])
        return f"EH-{num + 1:03d}"
    except Exception:
        return "EH-001"


def add_order(order_data: list):
    add_row("Orders", order_data)


def update_order_status(order_id: str, status: str):
    record, index = find_row_by_id("Orders", "OrderID", order_id)
    if index:
        update_cell("Orders", index, "Status", status)
    else:
        logger.warning(f"update_order_status: Order '{order_id}' not found.")


def assign_editor_to_order(order_id: str, editor_id: str):
    record, index = find_row_by_id("Orders", "OrderID", order_id)
    if index:
        update_cell("Orders", index, "SelectedEditor", editor_id)
        update_cell("Orders", index, "Status", "Assigned")
    else:
        logger.warning(f"assign_editor_to_order: Order '{order_id}' not found.")


def get_order(order_id: str):
    record, _ = find_row_by_id("Orders", "OrderID", order_id)
    return record


def get_client_record(client_id):
    record, _ = find_row_by_id("Clients", "Client", client_id)
    return record


def add_client(client_data: list):
    add_row("Clients", client_data)


def upsert_client(client_id: str, username: str):
    try:
        record, index = find_row_by_id("Clients", "Client", client_id)
        if record is None:
            add_row("Clients", [client_id, username, 1, "Normal", "-", 0, datetime.now().strftime("%Y-%m-%d %H:%M")])
            logger.info(f"New client created: {client_id} (@{username})")
        else:
            current_orders = int(record.get("Orders", 0))
            update_cell("Clients", index, "Orders", current_orders + 1)
            logger.info(f"Client {client_id} order count updated to {current_orders + 1}")
    except Exception as e:
        logger.error(f"upsert_client failed for {client_id}: {e}")


def add_application(app_data: list):
    add_row("Applications", app_data)


def get_applications(order_id: str) -> list:
    records = get_all_records("Applications")
    return [r for r in records if str(r.get("OrderID")) == str(order_id)]


def delete_applications_for_order(order_id: str):
    sheet = get_sheet("Applications")
    if not sheet:
        return
    records = sheet.get_all_records()
    for index in range(len(records) + 1, 1, -1):
        try:
            val = sheet.cell(index, 1).value
            if val == order_id:
                sheet.delete_rows(index)
        except Exception:
            pass


def get_editor(editor_id):
    record, _ = find_row_by_id("Editors", "Editor", editor_id)
    return record


def add_editor(editor_data: list):
    add_row("Editors", editor_data)


def update_editor_aura(editor_id, points_change: int):
    record, index = find_row_by_id("Editors", "Editor", editor_id)
    if index:
        current_aura = int(record.get("Aura", 0))
        new_aura = current_aura + points_change
        update_cell("Editors", index, "Aura", new_aura)
        return new_aura
    return None


def add_submission(submission_data: list):
    add_row("Submissions", submission_data)


def add_profit(profit_data: list):
    add_row("Profit", profit_data)
