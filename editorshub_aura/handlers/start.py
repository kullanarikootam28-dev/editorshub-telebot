from telegram import Update
from telegram.ext import ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to EditorsHub-AURA!\n\n"
        "Here's what you can do:\n\n"
        "👤 <b>Clients</b>\n"
        "  /order — Place a new order\n"
        "  /myorders — View your orders\n\n"
        "🎬 <b>Editors</b>\n"
        "  /register — Join as an editor\n"
        "  /appliedjobs — View your jobs\n"
        "  /leaderboard — See top editors\n\n"
        "🔧 <b>Admins</b>\n"
        "  /dashboard — Admin panel",
        parse_mode="HTML"
    )
