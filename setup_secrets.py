"""
GitHub Secrets Auto-Setup
Run this once to push all secrets to your GitHub repo automatically.

Install deps first:
    pip install PyNaCl requests

Then run:
    python setup_secrets.py
"""

import base64
import json
import os
import sys
import getpass

try:
    import requests
    from nacl import encoding, public
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install PyNaCl requests")
    import requests
    from nacl import encoding, public


REPO = "kullanarikootam28-dev/editorshub-telebot"
API  = "https://api.github.com"


def encrypt_secret(public_key_value: str, secret_value: str) -> str:
    pk = public.PublicKey(public_key_value.encode(), encoding.Base64Encoder())
    box = public.SealedBox(pk)
    encrypted = box.encrypt(secret_value.encode())
    return base64.b64encode(encrypted).decode()


def get_repo_public_key(token: str):
    r = requests.get(
        f"{API}/repos/{REPO}/actions/secrets/public-key",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
    )
    r.raise_for_status()
    return r.json()


def set_secret(token: str, key_id: str, public_key: str, name: str, value: str):
    encrypted = encrypt_secret(public_key, value)
    r = requests.put(
        f"{API}/repos/{REPO}/actions/secrets/{name}",
        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
        json={"encrypted_value": encrypted, "key_id": key_id},
    )
    if r.status_code in (201, 204):
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} — {r.status_code}: {r.text}")


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    if default:
        label = f"{label} [{default}]"
    label += ": "
    if secret:
        val = getpass.getpass(label)
    else:
        val = input(label)
    return val.strip() or default


def main():
    print("=" * 55)
    print("  EditorsHub Bot — GitHub Secrets Auto-Setup")
    print("=" * 55)
    print()
    print("You need a GitHub Personal Access Token (PAT) with")
    print("'repo' scope. Get one at:")
    print("  https://github.com/settings/tokens/new")
    print("  → Scopes: check 'repo'")
    print()

    token = prompt("GitHub PAT", secret=True)
    if not token:
        print("No token provided. Exiting.")
        sys.exit(1)

    # Verify token works
    r = requests.get(f"{API}/repos/{REPO}",
                     headers={"Authorization": f"token {token}"})
    if r.status_code != 200:
        print(f"❌ Token invalid or no access to repo ({r.status_code})")
        sys.exit(1)
    print(f"✅ Connected to {REPO}\n")

    # Get repo encryption key
    key_data   = get_repo_public_key(token)
    key_id     = key_data["key_id"]
    public_key = key_data["key"]

    print("Enter each secret value. Press Enter to skip (keeps existing value).")
    print()

    secrets = {}

    secrets["BOT_TOKEN"] = prompt("BOT_TOKEN (from @BotFather)", secret=True)
    secrets["SUPER_ADMIN_ID"] = prompt("SUPER_ADMIN_ID", default="7805721542")
    secrets["ADMIN_ID"] = prompt("ADMIN_ID", default="7805721542")
    secrets["JOBS_CHANNEL_ID"] = prompt("JOBS_CHANNEL_ID", default="-1003732177627")
    secrets["EDITORS_COMMUNITY_ID"] = prompt("EDITORS_COMMUNITY_ID")
    secrets["GOOGLE_SHEET_KEY"] = prompt(
        "GOOGLE_SHEET_KEY",
        default="1UXqPq2l5An_Xhcl9F23juZVZ0o99fvXllKrWMYLzN5w"
    )

    print()
    print("GOOGLE_CREDENTIALS — paste your full service account JSON,")
    print("then press Enter twice when done:")
    lines = []
    while True:
        line = input()
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    google_creds = "\n".join(lines).strip()
    if google_creds:
        # Validate it's valid JSON
        try:
            json.loads(google_creds)
            secrets["GOOGLE_CREDENTIALS"] = google_creds
        except json.JSONDecodeError:
            print("⚠️  Invalid JSON — GOOGLE_CREDENTIALS skipped")

    print()
    secrets["OPENAI_API_KEY"] = prompt("OPENAI_API_KEY (from platform.openai.com)", secret=True)

    print()
    print("Setting secrets...")
    for name, value in secrets.items():
        if value:
            set_secret(token, key_id, public_key, name, value)
        else:
            print(f"  ⏭️  {name} skipped")

    print()
    print("Done! Go to GitHub Actions → Run workflow to start the bot.")


if __name__ == "__main__":
    main()
