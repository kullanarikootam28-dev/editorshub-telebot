# EditorsHub-AURA Telegram Bot

A fully automated Telegram bot marketplace for video editing projects. Built for seamless client orders, editor recruitment, job assignment, and payment tracking.

## Features
- Client order flow with approval and tracking
- Editor registration, skill test, and leaderboard
- Admin dashboard for managing orders, assignments, and revenue
- Google Sheets integration for persistent data
- Secure payment collection and assignment logic
- Robust error handling and crash notifications

## Project Structure
```
editorshub_aura/
├ bot.py                # Main bot entrypoint
├ config.py             # Environment/config loader
├ render.yaml           # Render cloud deployment config
├ requirements.txt      # Python dependencies
├ database/
│  └ sheets.py          # Google Sheets integration
├ handlers/
│  ├ admin.py           # Admin dashboard & actions
│  ├ client.py          # Client order flow
│  ├ editor.py          # Editor registration & jobs
│  ├ relay.py           # Secure client-editor messaging
│  ├ admin_post.py      # Admin project posting
│  └ auth.py            # Admin access management
├ services/
│  ├ aura.py            # Editor reputation logic
│  ├ revenue.py         # Margin calculation
│  └ scheduler.py       # Scheduled tasks
├ utils/
│  ├ auth.py            # Admin checks
│  ├ keyboards.py       # Telegram keyboards
│  └ id_generator.py    # Order ID generator
├ health/
│  └ server.py          # Flask health endpoint
├ credentials.json      # Google Service Account (sample, redact secrets)
├ start_bot.bat         # Local dev auto-restart script
```

## Setup & Deployment
1. **Clone the repo:**
   ```
   git clone https://github.com/kullanarikootam28-dev/editorshub-telebot.git
   cd editorshub-telebot/editorshub_aura
   ```
2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
3. **Configure environment variables:**
   - Set up your Telegram bot token, admin ID, channel IDs, Google Sheet key, and Google credentials in Render's dashboard.
   - Do NOT commit `.env` with secrets.
4. **Deploy to Render:**
   - Render will use `render.yaml` to build and start the bot.
   - Add all environment variables in Render dashboard.

## Usage
- Start the bot with `/start` in Telegram.
- Admins use `/dashboard` for management.
- Editors use `/register` and `/appliedjobs`.
- Clients use `/order` and `/myorders`.

## License
MIT License

---
For support, contact @Nithinvijay on Telegram.
