"""
Admin auth — backed by a Google Sheets "Admins" tab so promotions/demotions
survive deploys and container restarts.

Sheet layout (tab name: Admins):
  Column A header: UserID
  Each subsequent row: a single Telegram user ID (as a string)
"""

import logging
from config import SUPER_ADMIN_ID, ADMIN_ID

logger = logging.getLogger(__name__)

# In-memory cache so we don't hit Sheets on every message
_admins_cache: list[str] | None = None


def _load_admins() -> list[str]:
    global _admins_cache
    if _admins_cache is not None:
        return _admins_cache

    try:
        from database.sheets import get_all_records
        records = get_all_records("Admins")
        ids = [str(r.get("UserID", "")).strip() for r in records if r.get("UserID")]
    except Exception as e:
        logger.error(f"Could not load Admins sheet: {e}. Falling back to defaults.")
        ids = []

    # Always include the two bootstrap admins
    defaults = [str(SUPER_ADMIN_ID)]
    if ADMIN_ID:
        defaults.append(str(ADMIN_ID))

    for d in defaults:
        if d not in ids:
            ids.append(d)

    _admins_cache = ids
    return _admins_cache


def _save_admin_to_sheet(user_id: str):
    try:
        from database.sheets import add_row
        add_row("Admins", [user_id])
    except Exception as e:
        logger.error(f"Could not write admin {user_id} to Admins sheet: {e}")


def _remove_admin_from_sheet(user_id: str):
    try:
        from database.sheets import get_sheet
        sheet = get_sheet("Admins")
        if not sheet:
            return
        records = sheet.get_all_records()
        for idx, row in enumerate(records, start=2):
            if str(row.get("UserID", "")).strip() == user_id:
                sheet.delete_rows(idx)
                break
    except Exception as e:
        logger.error(f"Could not remove admin {user_id} from Admins sheet: {e}")


def _invalidate_cache():
    global _admins_cache
    _admins_cache = None


def is_admin(user_id: int) -> bool:
    uid = str(user_id)
    if uid == str(SUPER_ADMIN_ID):
        return True
    return uid in _load_admins()


def add_admin(user_id: int) -> bool:
    uid = str(user_id)
    admins = _load_admins()
    if uid in admins:
        return False
    _save_admin_to_sheet(uid)
    _invalidate_cache()
    return True


def remove_admin(user_id: int) -> bool:
    uid = str(user_id)
    if uid == str(SUPER_ADMIN_ID):
        return False
    admins = _load_admins()
    if uid not in admins:
        return False
    _remove_admin_from_sheet(uid)
    _invalidate_cache()
    return True
