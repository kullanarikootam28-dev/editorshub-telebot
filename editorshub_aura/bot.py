import logging
import sys
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    Application,
    CommandHandler,
    CallbackQueryHandler,
    AIORateLimiter,
)

from config import BOT_TOKEN, ADMIN_ID
from health.server import start_health_server

# Handlers
from handlers.client import get_order_conv_handler, client_editor_selection, client_revision_decision, my_orders
from handlers.editor import get_submit_handler, leaderboard, get_register_conv_handler, applied_jobs, get_complaint_handler
from handlers.admin import admin_callback, admin_dashboard
from handlers.auth import manage_command, promote_reply_command, demote_reply_command, auth_callback
from handlers.admin_post import get_admin_post_handler
from handlers.relay import get_relay_conv_handler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# =========================
# START COMMAND
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Apply as Editor", callback_data="start_editor_registration")],
        [InlineKeyboardButton("Order a Project", callback_data="start_order_flow")],
        [InlineKeyboardButton("Editor Guidelines", callback_data="editor_guidelines")],
        [InlineKeyboardButton("Contact Admin", callback_data="contact_admin")]
    ]

    await update.message.reply_text(
        "Welcome to EditorsHub-AURA!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================
# CALLBACKS
# =========================
async def simple_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "editor_guidelines":
        await query.message.reply_text("Editor rules: finish on time, no direct contact.")

    elif query.data == "contact_admin":
        await query.message.reply_text("Contact: @Nithinvijay")


# =========================
# ERROR HANDLER
# =========================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception occurred", exc_info=context.error)

    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Bot crashed:\n{context.error}"
            )
        except Exception:
            pass


# =========================
# ✅ SAFE STARTUP (IMPORTANT)
# =========================
async def setup_bot(application):
    """
    This runs AFTER event loop starts.
    Scheduler must be started HERE.
    """

    from services.scheduler import start_scheduler

    # ✅ SAFE scheduler start
    start_scheduler(application)

    from telegram import BotCommand, BotCommandScopeDefault

    commands = [
        BotCommand("start", "Start bot"),
        BotCommand("order", "Place order"),
        BotCommand("myorders", "Track orders"),
    ]

    try:
        await application.bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    except Exception as e:
        logger.error(f"Command setup failed: {e}")


# =========================
# MAIN FUNCTION
# =========================
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing")
        return

    # Optional health server
    if os.getenv("RENDER") == "true":
        start_health_server()

    logger.info("Initializing bot...")

    app = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dashboard", admin_dashboard))
    app.add_handler(CommandHandler("myorders", my_orders))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("appliedjobs", applied_jobs))
    app.add_handler(CommandHandler("manage", manage_command))
    app.add_handler(CommandHandler("promote", promote_reply_command))
    app.add_handler(CommandHandler("demote", demote_reply_command))
    app.add_handler(get_complaint_handler())

    # Conversations
    app.add_handler(get_admin_post_handler())
    app.add_handler(get_order_conv_handler())
    app.add_handler(get_submit_handler())
    app.add_handler(get_register_conv_handler())
    app.add_handler(get_relay_conv_handler())

    # Callbacks
    app.add_handler(CallbackQueryHandler(simple_callbacks))
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(CallbackQueryHandler(auth_callback, pattern="^auth\\|"))
    app.add_handler(CallbackQueryHandler(client_editor_selection, pattern="^select_editor\\|"))
    app.add_handler(CallbackQueryHandler(client_revision_decision, pattern="^(req_revision|rate)\\|"))

    # Error handler
    app.add_error_handler(error_handler)

    # ✅ CRITICAL: run setup AFTER loop starts
    app.post_init = setup_bot

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
