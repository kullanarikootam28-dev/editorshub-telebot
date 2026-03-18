import logging
import sys
import os

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    AIORateLimiter,
    ContextTypes,
)
from telegram import Update

from config import BOT_TOKEN, ADMIN_ID
from health.server import start_health_server

# handlers
from handlers.client import get_order_conv_handler, my_orders
from handlers.editor import leaderboard, applied_jobs, get_register_conv_handler, get_submit_handler, get_complaint_handler
from handlers.admin import admin_dashboard, admin_callback
from handlers.auth import manage_command, promote_reply_command, demote_reply_command, auth_callback
from handlers.admin_post import get_admin_post_handler
from handlers.relay import get_relay_conv_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =========================
# BASIC COMMAND
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running ✅")


# =========================
# ERROR HANDLER
# =========================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error occurred", exc_info=context.error)


# =========================
# ✅ SAFE STARTUP
# =========================
async def setup_bot(application):
    from services.scheduler import start_scheduler

    # ✅ start scheduler AFTER event loop exists
    start_scheduler(application)

    logger.info("✅ Scheduler started safely after event loop.")

# =========================
# MAIN
# =========================
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing")
        return

    # optional
    if os.getenv("RENDER") == "true":
        start_health_server()

    app = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", admin_dashboard))
    app.add_handler(CommandHandler("myorders", my_orders))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("appliedjobs", applied_jobs))
    app.add_handler(CommandHandler("manage", manage_command))
    app.add_handler(CommandHandler("promote", promote_reply_command))
    app.add_handler(CommandHandler("demote", demote_reply_command))
    app.add_handler(get_complaint_handler())

    app.add_handler(get_admin_post_handler())
    app.add_handler(get_order_conv_handler())
    app.add_handler(get_submit_handler())
    app.add_handler(get_register_conv_handler())
    app.add_handler(get_relay_conv_handler())

    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(CallbackQueryHandler(auth_callback))

    app.add_error_handler(error_handler)

    # ✅ THIS IS CRITICAL
    app.post_init = setup_bot

    logger.info("Starting bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
