"""
Run this once to create all required Google Sheets tabs with correct headers.
Also called automatically on bot startup to create any missing sheets.

Usage (one-time manual run):
    cd editorshub_aura
    python setup_sheets.py
"""

import sys
import logging
from database.sheets import get_client, _get_spreadsheet

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ── Sheet definitions ─────────────────────────────────────────────────────────
# Each entry: (sheet_name, [column_headers])
SHEETS = [
    (
        "Orders",
        [
            "OrderID", "Client", "Category", "Duration", "Videos",
            "ClientBudget", "EditorBudget", "Profit", "Deadline",
            "RawFiles", "Reference", "Status", "SubmissionDate",
            "Payment", "SelectedEditor", "CreatedAt",
        ],
    ),
    (
        "Clients",
        ["Client", "Username", "Orders", "Tier", "Notes", "TotalSpent", "JoinedAt"],
    ),
    (
        "Editors",
        ["Editor", "Username", "Skill", "Software", "Portfolio", "Aura", "Rating", "JoinedAt"],
    ),
    (
        "Applications",
        ["OrderID", "Editor", "Portfolio", "AppliedAt"],
    ),
    (
        "Submissions",
        ["OrderID", "Editor", "Link", "Approved", "Paid", "SubmittedAt"],
    ),
    (
        "Profit",
        ["OrderID", "Amount", "Date"],
    ),
    (
        "Admins",
        ["UserID"],
    ),
    (
        "Moderation",
        ["Timestamp", "UserID", "Username", "Message", "Categories", "Location", "Action"],
    ),
]


def setup(spreadsheet=None):
    """
    Create any missing sheets and add headers.
    Skips sheets that already exist (safe to run multiple times).
    Returns (created_count, skipped_count).
    """
    if spreadsheet is None:
        spreadsheet = _get_spreadsheet()
        if not spreadsheet:
            logger.error("Could not connect to Google Sheets. Check credentials.")
            return 0, 0

    existing = {ws.title for ws in spreadsheet.worksheets()}
    created, skipped = 0, 0

    for sheet_name, headers in SHEETS:
        if sheet_name in existing:
            logger.info(f"  ✅ '{sheet_name}' already exists — skipped")
            skipped += 1
            continue

        try:
            ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
            ws.append_row(headers, value_input_option="USER_ENTERED")
            logger.info(f"  ✨ Created '{sheet_name}' with {len(headers)} columns")
            created += 1
        except Exception as e:
            logger.error(f"  ❌ Failed to create '{sheet_name}': {e}")

    return created, skipped


if __name__ == "__main__":
    import os, json
    from dotenv import load_dotenv
    load_dotenv()

    logger.info("=" * 50)
    logger.info("EditorsHub-AURA — Google Sheets Setup")
    logger.info("=" * 50)

    spreadsheet = _get_spreadsheet()
    if not spreadsheet:
        logger.error("Cannot open spreadsheet. Check GOOGLE_CREDENTIALS and GOOGLE_SHEET_KEY.")
        sys.exit(1)

    logger.info(f"Connected to: {spreadsheet.title}")
    logger.info("Checking sheets...\n")

    created, skipped = setup(spreadsheet)

    logger.info(f"\nDone. Created: {created}  |  Already existed: {skipped}")
    logger.info("Your Google Sheet is ready.")
