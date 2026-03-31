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


def get_client():
    try:
        if GOOGLE_CREDENTIALS:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                GOOGLE_CREDENTIALS, scope
            )
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                GOOGLE_CREDENTIALS_FILE, scope
            )
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Failed to authenticate Google Sheets: {e}")
        return None


def get_sheet(sheet_name: str):
    client = get_client()
    if client and GOOGLE_SHEET_KEY:
        try:
            spreadsheet = client.open_by_key(GOOGLE_SHEET_KEY)
            return spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.error(f"Worksheet '{sheet_name}' not found in spreadsheet.")
            return None
        except Exception as e:
            logger.error(f"Failed to open sheet '{sheet_name}': {e}")
            return None
    return None


def add_row(sheet_name: str, row_data: list):
    """Append a row. Raises on failure so callers know the write failed."""
    sheet = get_sheet(sheet_name)
    if not sheet:
        raise RuntimeError(
            f"Could not open sheet '{sheet_name}'. Check credentials and sheet name."
        )
    try:
        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        logger.info(f"Row added to '{sheet_name}': {row_data}")
    except Exception as e:
        logger.error(f"Failed to append row to '{sheet_name}': {e}")
        raise


def get_all_records(sheet_name: str) -> list:
    sheet = get_sheet(sheet_name)
    if sheet:
        try:
            return sheet.get_all_records()
        except Exception as e:
            logger.error(f"Failed to get records from '{sheet_name}': {e}")
    return []


def find_row_by_id(sheet_name: str, id_col_name: str, id_value):
    records = get_all_records(sheet_name)
    for index, record in enumerate(records, start=2):  # +2: 1-indexed + header row
        if str(record.get(id_col_name)) == str(id_value):
            return record, index
    return None, None


def update_cell(sheet_name: str, row_index: int, col_name: str, value):
    sheet = get_sheet(sheet_name)
    if sheet:
        try:
            header = sheet.row_values(1)
            if col_name in header:
                col_index = header.index(col_name) + 1
                sheet.update_cell(row_index, col_index, value)
            else:
                logger.warning(
                    f"Column '{col_name}' not found in '{sheet_name}'. Headers: {header}"
                )
        except Exception as e:
            logger.error(
                f"Failed to update cell in '{sheet_name}' row {row_index} col '{col_name}': {e}"
            )


# ── Order Helpers ─────────────────────────────────────────────────────────────

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
    """
    Columns: [OrderID, Client, Category, Duration, Videos, ClientBudget,
              EditorBudget, PlatformProfit, Deadline, RawFiles, Reference,
              Status, SelectedEditor, PaymentStatus, RevisionStatus, CreatedAt]
    """
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


# ── Client Helpers ────────────────────────────────────────────────────────────

def get_client_record(client_id):
    record, _ = find_row_by_id("Clients", "Client", client_id)
    return record


def add_client(client_data: list):
    """Columns: [Client, Username, Orders, Priority, AvgRating, TotalSpent, JoinedAt]"""
    add_row("Clients", client_data)


def upsert_client(client_id: str, username: str):
    """Creates a new client row or increments their Orders count."""
    try:
        record, index = find_row_by_id("Clients", "Client", client_id)
        if record is None:
            add_row(
                "Clients",
                [
                    client_id,
                    username,
                    1,
                    "Normal",
                    "-",
                    0,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ],
            )
            logger.info(f"New client created: {client_id} (@{username})")
        else:
            current_orders = int(record.get("Orders", 0))
            update_cell("Clients", index, "Orders", current_orders + 1)
            logger.info(
                f"Client {client_id} order count updated to {current_orders + 1}"
            )
    except Exception as e:
        logger.error(f"upsert_client failed for {client_id}: {e}")


# ── Application Helpers ───────────────────────────────────────────────────────

def add_application(app_data: list):
    """Columns: [OrderID, Editor, Portfolio, Aura, Rating, AppliedAt]"""
    add_row("Applications", app_data)


def get_applications(order_id: str) -> list:
    records = get_all_records("Applications")
    return [r for r in records if str(r.get("OrderID")) == str(order_id)]


def delete_applications_for_order(order_id: str):
    sheet = get_sheet("Applications")
    if not sheet:
        return
    records = sheet.get_all_records()
    # Iterate in reverse so row deletions don't shift indices
    for index in range(len(records) + 1, 1, -1):
        try:
            val = sheet.cell(index, 1).value
            if val == order_id:
                sheet.delete_rows(index)
        except Exception:
            pass


# ── Editor Helpers ────────────────────────────────────────────────────────────

def get_editor(editor_id):
    record, _ = find_row_by_id("Editors", "Editor", editor_id)
    return record


def add_editor(editor_data: list):
    """Columns: [Editor, Username, Category, Portfolio, Aura, Rating, CompletedJobs, ActiveJobs, JoinedAt]"""
    add_row("Editors", editor_data)


def update_editor_aura(editor_id, points_change: int):
    record, index = find_row_by_id("Editors", "Editor", editor_id)
    if index:
        current_aura = int(record.get("Aura", 0))
        new_aura = current_aura + points_change
        update_cell("Editors", index, "Aura", new_aura)
        return new_aura
    return None


# ── Submission & Profit Helpers ───────────────────────────────────────────────

def add_submission(submission_data: list):
    """Columns: [OrderID, Editor, SubmissionLink, RevisionRequested, FinalApproved, SubmittedAt]"""
    add_row("Submissions", submission_data)


def add_profit(profit_data: list):
    """Columns: [OrderID, Client, Editor, EditorPayment, Profit, Date]"""
    add_row("Profit", profit_data)
