import logging
import sys
import traceback
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, Application, CommandHandler, CallbackQueryHandler, AIORateLimiter

from config import BOT_TOKEN, ADMIN_ID
from health.server import start_health_server

from handlers.client import get_order_conv_handler, client_editor_selection, client_revision_decision
from handlers.editor import get_submit_handler, leaderboard, get_register_conv_handler
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
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    # Handle deep link from channel for editor applying
    if args and args[0].startswith("apply_"):
        order_id = args[0][len("apply_"):]
        editor_id = str(update.message.from_user.id)
        editor_username = update.message.from_user.username or "Unknown"
        editor_name = update.message.from_user.first_name or editor_username
        
        from database.sheets import add_application, get_applications, find_row_by_id
        from datetime import datetime
        
        # Check: Must be a registered editor
        editor_rec, editor_idx = find_row_by_id("Editors", "Editor", editor_id)
        if not editor_idx:
            await update.message.reply_text(
                "⚠️ You need to be a registered Editor to apply for jobs.\n\n"
                "Use /register to start your recruitment process.",
                parse_mode="Markdown"
            )
            return
        
        # Check: Duplicate application guard
        existing_apps = get_applications(order_id)
        already_applied = any(str(a.get("Editor")) == editor_id for a in existing_apps)
        if already_applied:
            await update.message.reply_text(
                f"✋ *You have already applied for Order* `{order_id}`.\n\n"
                "Your application is being reviewed. We'll contact you if you're selected.",
                parse_mode="Markdown"
            )
            return
        
        add_application([order_id, editor_id, editor_username, "Pending Review", "-", datetime.now().strftime("%Y-%m-%d %H:%M")])
        
        await update.message.reply_text(
            f"✅ *Application Submitted!*\n\nYou have applied for Order `{order_id}`.\nThe Admin will review your application and get back to you.",
            parse_mode="Markdown"
        )
        
        if ADMIN_ID:
            from utils.keyboards import get_admin_grant_assignment_keyboard
            notif_text = (
                f"📥 *New Editor Application*\n\n"
                f"Order: `{order_id}`\n"
                f"Editor: @{editor_username} (ID: `{editor_id}`)\n"
                f"Name: {editor_name}\n"
                f"Applied at: {datetime.now().strftime('%H:%M')}"
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=notif_text,
                    parse_mode="Markdown",
                    reply_markup=get_admin_grant_assignment_keyboard(order_id, editor_id)
                )
                logger.info(f"Admin notified of application: editor={editor_id} order={order_id}")
            except Exception as e:
                logger.error(f"FAILED to notify admin of application. ADMIN_ID={ADMIN_ID}, error={e}")
        return

    # Main Menu
    keyboard = [
        [InlineKeyboardButton("📝 Apply as Editor", callback_data="start_editor_registration")],
        [InlineKeyboardButton("🎬 Order a Project", callback_data="start_order_flow")],
        [InlineKeyboardButton("📜 Editor Guidelines", callback_data="editor_guidelines")],
        [InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to EditorsHub-AURA!\nPlease choose an option below:", reply_markup=reply_markup)

async def simple_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "editor_guidelines":
        await query.message.reply_text("Editor Guidelines:\n1. Revisions must be completed within 24h.\n2. Do NOT contact clients directly. [If violated, you will be expelled from the community]\n3. Late delivery deducts 10 AURA.")
    elif query.data == "contact_admin":
        await query.message.reply_text("Support needed? Send your message to @Nithinvijay")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    
    message = (
        "⚠️ *Bot Crashed!*\n\n"
        f"An error occurred.\n"
        f"Error: `{context.error}`\n\n"
        "All users: Please wait up to 12 hours while the admin fixes the issue. Do not retry until you see the bot online again."
    )
    
    # Notify Admin
    if ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode="Markdown")
        except Exception:
            pass
            
    # Notify the user so they aren't left hanging
    if isinstance(update, Update):
        error_msg = (
            "⚠️ Bot is currently unavailable due to a crash.\n"
            "The admin has been notified. Please wait up to 12 hours for a fix.\n"
            "Do not retry until the bot is online again."
        )
        try:
            if update.callback_query:
                await update.callback_query.answer("⚠️ Bot crashed. Please wait up to 12 hours for admin fix.", show_alert=True)
            elif update.message:
                await update.message.reply_text(error_msg)
            elif update.edited_message:
                await update.edited_message.reply_text(error_msg)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing! Cannot start the bot.")
        return
        
    from services.scheduler import start_scheduler
    
    logger.info("Starting Health Server...")
    start_health_server()
    
    logger.info("Initializing Bot...")
    app = Application.builder().token(BOT_TOKEN).rate_limiter(AIORateLimiter()).build()
    
    # Error Handler
    app.add_error_handler(error_handler)
    
    # Basic commands
    from handlers.admin import admin_dashboard
    from handlers.client import my_orders
    from handlers.editor import leaderboard, applied_jobs, get_complaint_handler

    app.add_handler(CommandHandler('dashboard', admin_dashboard))
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('myorders', my_orders))
    app.add_handler(CommandHandler('leaderboard', leaderboard))
    app.add_handler(CommandHandler('appliedjobs', applied_jobs))
    app.add_handler(get_complaint_handler())
    app.add_handler(CommandHandler('manage', manage_command))
    app.add_handler(CommandHandler('promote', promote_reply_command))
    app.add_handler(CommandHandler('demote', demote_reply_command))
    
    # Conversation Handlers — admin_post must be first to take priority
    app.add_handler(get_admin_post_handler())
    app.add_handler(get_order_conv_handler())
    app.add_handler(get_submit_handler())
    app.add_handler(get_register_conv_handler())
    app.add_handler(get_relay_conv_handler())
    
    # Callback Query Handlers
    app.add_handler(CallbackQueryHandler(simple_callbacks, pattern=r'^(editor_guidelines|contact_admin)$'))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r'^(dashboard|approve_order|deny_order|fwd_client|grant_assignment|confirm_payment|payment_action|eval_editor)\|'))
    app.add_handler(CallbackQueryHandler(auth_callback, pattern=r'^auth\|'))
    app.add_handler(CallbackQueryHandler(client_editor_selection, pattern=r'^select_editor\|'))
    app.add_handler(CallbackQueryHandler(client_revision_decision, pattern=r'^(req_revision|rate)\|'))
    
    logger.info("Starting scheduler...")
    start_scheduler(app)

    async def setup_bot(application):
        """On startup, configure commands, menu button, and pin the Admin Control Panel."""
        from telegram import BotCommand, BotCommandScopeDefault, BotCommandScopeChat, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, MenuButtonCommands
        
        # Set default commands for all users
        default_commands = [
            BotCommand("start", "Welcome & Main Menu"),
            BotCommand("order", "Place a new editing request"),
            BotCommand("myorders", "Check status of your orders"),
            BotCommand("complaint", "Submit a complaint or feedback")
        ]
        try:
            # Send to default, private chats, and groups to ensure Menu Button is visible EVERYWHERE
            await application.bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
            await application.bot.set_my_commands(default_commands, scope=BotCommandScopeAllPrivateChats())
            await application.bot.set_my_commands(default_commands, scope=BotCommandScopeAllGroupChats())
            
            # Explicitly set the chat menu button to show the Commands menu
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            logger.info("Bot commands and Menu Button registered across all scopes.")
        except Exception as e:
            logger.error(f"Could not set default commands: {e}")

        # Set specific commands for Editors Hub Jobs Channel
        from config import JOBS_CHANNEL_ID
        if JOBS_CHANNEL_ID:
            try:
                editor_commands = [
                    BotCommand("appliedjobs", "View the jobs you applied for"),
                    BotCommand("leaderboard", "Top 10 Editors by Aura"),
                    BotCommand("complaint", "Contact Admin / Report an issue")
                ]
                await application.bot.set_my_commands(
                    editor_commands,
                    scope=BotCommandScopeChat(chat_id=JOBS_CHANNEL_ID)
                )
            except Exception as e:
                logger.error(f"Could not set jobs channel commands: {e}")

        if not ADMIN_ID:
            return

        # Set admin commands specifically for the admin group
        try:
            admin_commands = [
                BotCommand("dashboard", "Open Admin Dashboard"),
                BotCommand("manage", "Manage Editor limits"),
                BotCommand("promote", "Promote a user (reply)"),
                BotCommand("demote", "Demote an Editor (reply)"),
            ]
            await application.bot.set_my_commands(
                default_commands + admin_commands, 
                scope=BotCommandScopeChat(chat_id=ADMIN_ID)
            )
        except Exception as e:
            logger.error(f"Could not set admin commands: {e}")

        # Pin Admin Control Panel
        try:
            from utils.keyboards import get_admin_dashboard_keyboard
            panel_text = (
                "🎛️ *ADMIN CONTROL PANEL*\n\n"
                "Tap any button below to manage your bot.\n"
                "This panel is always pinned at the top of this group."
            )
            msg = await application.bot.send_message(
                chat_id=ADMIN_ID,
                text=panel_text,
                parse_mode="Markdown",
                reply_markup=get_admin_dashboard_keyboard()
            )
            await application.bot.pin_chat_message(
                chat_id=ADMIN_ID,
                message_id=msg.message_id,
                disable_notification=True
            )
            logger.info("Admin Control Panel pinned successfully.")
        except Exception as e:
            logger.error(f"Could not pin control panel: {e}")

    app.post_init = setup_bot

    logger.info("Starting bot polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
