import json
import os
from config import SUPER_ADMIN_ID, ADMIN_ID

ADMINS_FILE = "admins.json"

def _load_admins():
    if not os.path.exists(ADMINS_FILE):
        # Default starting admins: the Super Admin and the configured ADMIN_ID
        return [str(SUPER_ADMIN_ID), str(ADMIN_ID)]
    
    try:
        with open(ADMINS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return [str(SUPER_ADMIN_ID), str(ADMIN_ID)]

def _save_admins(admins_list):
    with open(ADMINS_FILE, 'w') as f:
        json.dump(admins_list, f, indent=4)

def is_admin(user_id: int) -> bool:
    """Checks if a user is in the authorized admins list."""
    uid = str(user_id)
    if uid == str(SUPER_ADMIN_ID):
        return True # Super admin always authorized
    
    admins = _load_admins()
    return uid in admins

def add_admin(user_id: int) -> bool:
    uid = str(user_id)
    admins = _load_admins()
    if uid not in admins:
        admins.append(uid)
        _save_admins(admins)
        return True
    return False

def remove_admin(user_id: int) -> bool:
    uid = str(user_id)
    if uid == str(SUPER_ADMIN_ID):
        return False # Cannot remove Super Admin
        
    admins = _load_admins()
    if uid in admins:
        admins.remove(uid)
        _save_admins(admins)
        return True
    return False
