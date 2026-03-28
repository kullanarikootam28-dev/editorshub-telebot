import logging
import sys
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    AIORateLimiter,
)

from config import BOT_TOKEN
from health.server import start_health_server

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

async def post_init(application: Application) -> None:
    """This runs AFTER the event loop is started and the bot is ready."""
    from services.scheduler import start_scheduler
    logger.info("Bot initialized. Starting scheduler...")
    start_scheduler(application)

async def error_handler(update: object, context: object):
    logger.error("Exception:", exc_info=context.error)

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN missing")
        return

    # 1. Start Flask Health Server in background thread
    logger.info("Starting Health Server...")
    start_health_server() 

    # 2. Build Application with post_init hook
    logger.info("Initializing Bot...")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .post_init(post_init)  # <--- CRITICAL FIX: Scheduler starts here
        .build()
    )

    # 3. Add Error Handler
    app.add_error_handler(error_handler)

    # 4. Import and Register Handlers
    from handlers.client import my_orders, get_order_conv_handler, client_editor_selection, client_revision_decision
    from handlers.editor import applied_jobs, get_complaint_handler, leaderboard, get_submit_handler, get_register_conv_handler
    from handlers.admin import admin_callback, admin_dashboard
    from handlers.auth import manage_command, promote_reply_command, demote_reply_command, auth_callback
    from handlers.admin_post import get_admin_post_handler
    from handlers.relay import get_relay_conv_handler

    # Commands
    app.add_handler(CommandHandler("dashboard", admin_dashboard))
    app.add_handler(CommandHandler("myorders", my_orders))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("appliedjobs", applied_jobs))
    app.add_handler(get_complaint_handler())
    app.add_handler(CommandHandler("manage", manage_command))
    app.add_handler(CommandHandler("promote", promote_reply_command))
    app.add_handler(CommandHandler("demote", demote_reply_command))

    # Conversations
    app.add_handler(get_admin_post_handler())
    app.add_handler(get_order_conv_handler())
    app.add_handler(get_submit_handler())
    app.add_handler(get_register_conv_handler())
    app.add_handler(get_relay_conv_handler())

    # Callbacks
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^(dashboard|approve_order|deny_order|fwd_client|grant_assignment|confirm_payment|payment_action|eval_editor)\|"))
    app.add_handler(CallbackQueryHandler(auth_callback, pattern=r"^auth\|"))
    app.add_handler(CallbackQueryHandler(client_editor_selection, pattern=r"^select_editor\|"))
    app.add_handler(CallbackQueryHandler(client_revision_decision, pattern=r"^(req_revision|rate)\|"))

    # 5. Start Polling (Blocking call)
    logger.info("Starting bot polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
