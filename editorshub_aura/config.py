import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── Bot ──────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")

# ── Admins ───────────────────────────────────────────────────────────────────
ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID", "7805721542")
if SUPER_ADMIN_ID:
    SUPER_ADMIN_ID = int(SUPER_ADMIN_ID)

# ── Channels ─────────────────────────────────────────────────────────────────
JOBS_CHANNEL_ID = os.getenv("JOBS_CHANNEL_ID")
if JOBS_CHANNEL_ID:
    if JOBS_CHANNEL_ID.lstrip("-").isdigit():
        JOBS_CHANNEL_ID = int(JOBS_CHANNEL_ID)

EDITORS_COMMUNITY_ID = os.getenv("EDITORS_COMMUNITY_ID")
if EDITORS_COMMUNITY_ID:
    if EDITORS_COMMUNITY_ID.lstrip("-").isdigit():
        EDITORS_COMMUNITY_ID = int(EDITORS_COMMUNITY_ID)

# ── Google Sheets ─────────────────────────────────────────────────────────────
GOOGLE_SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")

_google_creds_json = os.getenv("GOOGLE_CREDENTIALS")
GOOGLE_CREDENTIALS = json.loads(_google_creds_json) if _google_creds_json else None
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# ── Server (health check) ─────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", 8080))
