from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import datetime

from config import ADMIN_ID
from database.sheets import get_order, add_application, update_editor_aura, add_submission, update_order_status, add_editor, find_row_by_id

PORTFOLIO = 1
SUBMISSION_LINK = 2

# Removed get_job_apply_handler since it's handled via bot.py deep linking

# Real Test Footage link provided by admin
TEST_FOOTAGE_LINK = "https://drive.google.com/drive/folders/1vKusaQTLGjrSlpnr_G2xgUeJgxlxXFlP?usp=drive_link"

# Registration Flow States — 10-15 range to avoid conflicts
REG_NAME, REG_SKILL, REG_SOFTWARE, REG_PORTFOLIO, REG_TEST_SUBMISSION = range(10, 15)

async def start_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        msg = query.message
    else:
        msg = update.message
        
    editor_id = str(update.effective_user.id)
    record, index = find_row_by_id("Editors", "Editor", editor_id)
    if index:
        await msg.reply_text(
            "✋ You are already registered as an Editor!\n\n"
            "Use /appliedjobs to see your job applications or head to the Jobs Channel to find new orders."
        )
        return ConversationHandler.END
        
    await msg.reply_text(
        "👋 *Welcome to the EditorsHub-AURA Recruitment Process!*\n\n"
        "We'll walk you through a short sign-up and a quick skill test.\n\n"
        "First — what is your full name or editor alias?",
        parse_mode="Markdown"
    )
    return REG_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_name'] = update.message.text.strip()
    
    from utils.keyboards import get_editor_skills_keyboard
    await update.message.reply_text(
        "What is your primary editing skill?",
        reply_markup=get_editor_skills_keyboard()
    )
    return REG_SKILL

async def reg_skill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query:
        await query.answer()
        skill = query.data.split('|')[1]
        msg_obj = query.message
    else:
        skill = update.message.text.strip()
        msg_obj = update.message
        
    context.user_data['reg_skill'] = skill
    await msg_obj.reply_text(
        f"✅ Skill selected: *{skill}*\n\n"
        "What software do you primarily use?\n_(e.g. Premiere Pro, DaVinci Resolve, After Effects)_",
        parse_mode="Markdown"
    )
    return REG_SOFTWARE

async def reg_software(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_software'] = update.message.text.strip()
    await update.message.reply_text(
        "💼 Please share a link to your *portfolio*.\n\n"
        "_This can be a YouTube channel, Google Drive, Behance, or any link showing your previous work._",
        parse_mode="Markdown"
    )
    return REG_PORTFOLIO

async def reg_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['reg_portfolio'] = update.message.text.strip()
    
    await update.message.reply_text(
        "🎬 *Almost there — Skill Test!*\n\n"
        "To verify your editing skills, please download our test footage below and create a short edit.\n\n"
        f"📥 *Download Raw Footage (Reels & Long-form):*\n{TEST_FOOTAGE_LINK}\n\n"
        "📌 *Instructions:*\n"
        "• Edit the footage to showcase your best pacing, transitions, and colour grading.\n"
        "• You can submit *one* edit (reel style OR long form).\n\n"
        "Once done, upload it as an *unlisted YouTube video* or *Google Drive link* and reply with the link below:",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    return REG_TEST_SUBMISSION

async def reg_test_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    test_link = update.message.text.strip()
    name = context.user_data.get('reg_name')
    skill = context.user_data.get('reg_skill')
    software = context.user_data.get('reg_software')
    portfolio = context.user_data.get('reg_portfolio')
    editor_id = str(update.message.from_user.id)
    editor_username = update.message.from_user.username or "Unknown"
    
    # Final double-check: make sure not already registered
    record, index = find_row_by_id("Editors", "Editor", editor_id)
    if index:
        await update.message.reply_text("✋ You are already registered as an Editor!")
        return ConversationHandler.END
    
    # Send full summary to admin for review
    if ADMIN_ID:
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve & Add (50 Aura)", callback_data=f"eval_editor|approve|{editor_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"eval_editor|reject|{editor_id}")
                ]
            ]
            markup = InlineKeyboardMarkup(keyboard)
            
            # Use HTML parse mode — safe for URLs/underscores that break Markdown
            admin_text = (
                f"📥 <b>New Editor Test Submission</b>\n\n"
                f"👤 <b>Name:</b> {name}\n"
                f"🔖 <b>Username:</b> @{editor_username} (ID: <code>{editor_id}</code>)\n"
                f"🎬 <b>Skill:</b> {skill}\n"
                f"🛠 <b>Software:</b> {software}\n\n"
                f"💼 <b>Portfolio:</b> {portfolio}\n\n"
                f"🔗 <b>Test Video:</b> {test_link}\n\n"
                "Review the edit and portfolio, then choose an action:"
            )
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=markup
            )
            
            # Store temp data for the callback
            context.bot_data[f"temp_editor_{editor_id}"] = {
                "name": name,
                "username": editor_username,
                "skill": skill,
                "software": software,
                "portfolio": portfolio,
                "test_link": test_link
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"reg_test_submission admin notify failed: {e}")
            await update.message.reply_text(
                f"⚠️ Your submission was received but we couldn't notify the admin right now.\n"
                f"Please contact @Nithinvijay directly with this error: {e}"
            )
            return ConversationHandler.END
            
    await update.message.reply_text(
        f"✅ *Thank you, {name}!*\n\n"
        "Your test edit and portfolio have been submitted for review. 🎉\n\n"
        "Our Admin team will evaluate your work and contact you within 24-48 hours. "
        "Stay tuned!",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

def get_register_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler('register', start_register),
            CallbackQueryHandler(start_register, pattern=r'^start_editor_registration$')
        ],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_SKILL: [
                CallbackQueryHandler(reg_skill, pattern=r'^skill\|'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, reg_skill)
            ],
            REG_SOFTWARE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_software)],
            REG_PORTFOLIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_portfolio)],
            REG_TEST_SUBMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_test_submission)]
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)]
    )

# Submission Flow
async def start_submit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /submit ORDERID")
        return ConversationHandler.END
        
    order_id = context.args[0]
    context.user_data['submit_order_id'] = order_id
    await update.message.reply_text(f"Submitting for {order_id}. Please send the final delivery link:")
    return SUBMISSION_LINK

async def receive_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    order_id = context.user_data.get('submit_order_id')
    editor_id = str(update.message.from_user.id)
    
    submission_data = [
        order_id, editor_id, link, "No", "No", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ]
    add_submission(submission_data)
    update_order_status(order_id, "Submitted for Review")
    
    await update.message.reply_text("Submission received. Client has 24 hours to review.")
    
    # Notify admin
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Editor {editor_id} submitted work for {order_id}.\nLink: {link}"
            )
        except Exception:
            pass
        
    # Ask Client to review
    order = get_order(order_id)
    if order:
        client_id = order.get('Client')
        if client_id:
            from utils.keyboards import get_client_review_keyboard
            await context.bot.send_message(
                chat_id=client_id,
                text=f"Great news! Your video for Order {order_id} is ready.\n\nLink: {link}\n\nPlease review and rate the quality, or request a revision.",
                reply_markup=get_client_review_keyboard(order_id)
            )
            
    return ConversationHandler.END

def get_submit_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('submit', start_submit)],
        states={
            SUBMISSION_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_submission)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.sheets import get_all_records
    editors = get_all_records("Editors")
    if not editors:
        await update.message.reply_text("🏆 No editors found yet.")
        return
        
    # Sort by Aura descending
    valid_editors = []
    for e in editors:
        aura = str(e.get("Aura", "0")).strip()
        try:
            aura_int = int(aura)
            valid_editors.append((e, aura_int))
        except ValueError:
            valid_editors.append((e, 0))
            
    sorted_editors = sorted(valid_editors, key=lambda x: x[1], reverse=True)[:10]
    
    text = "🏆 <b>AURA Leaderboard Top 10</b>\n\n"
    for i, (e, aura) in enumerate(sorted_editors, 1):
        username = e.get("Username", "Unknown")
        rating = e.get("Rating", "5.0")
        text += f"{i}. <b>@{username}</b> — ⚡ {aura} Aura | ⭐ {rating}\n"
        
    await update.message.reply_text(text, parse_mode="HTML")

async def applied_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    editor_id = str(update.effective_user.id)
    from database.sheets import get_all_records
    applications = get_all_records("Applications")
    
    my_apps = [a for a in applications if str(a.get("Editor", "")).strip() == editor_id]
    
    if not my_apps:
        await update.message.reply_text("You haven't applied for any jobs yet.")
        return
        
    text = f"📋 <b>Your Applied Jobs ({len(my_apps)} total)</b>\n\n"
    for a in my_apps:
        order_id = a.get("OrderID", "Unknown")
        status = a.get("Aura", "Pending Review") # In sheets 'Aura' col in Applications is often used for status string... wait actually look at sheets.py
        # Actually sheets.py says: [OrderID, Editor, Portfolio, Aura, Rating, AppliedAt] 
        # But start_register sends: [order_id, editor_id, editor_username, "Pending Review", "-", date]
        # Therefore index 3 is status!
        
        # Let's get the real order status from the Orders sheet to be sure
        from database.sheets import get_order
        order = get_order(order_id)
        order_status = order.get("Status", "Unknown") if order else "Unknown"
        
        text += f"🔹 <b>Order {order_id}</b>\n"
        text += f"   System Status: <i>{order_status}</i>\n"
        text += f"   Applied On: {a.get('AppliedAt', '-')}\n\n"
        
    await update.message.reply_text(text, parse_mode="HTML")

# --- Complaint Flow ---
COMPLAINT_TEXT = 99
async def start_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 <b>Submit a Complaint / Feedback</b>\n\n"
        "Please type your message in a single text bubble below. This will be forwarded directly to the Admin.\n\n"
        "<i>Use /cancel to abort.</i>",
        parse_mode="HTML"
    )
    return COMPLAINT_TEXT

async def receive_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name
    
    await update.message.reply_text("✅ Your message has been securely forwarded to the Admin. Thank you!")
    
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚨 <b>NEW COMPLAINT / FEEDBACK</b>\n\nFrom: {username} (ID: `{user.id}`)\n\n💬 Message:\n{text}",
                parse_mode="HTML"
            )
        except Exception:
            pass
            
    return ConversationHandler.END

def get_complaint_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('complaint', start_complaint)],
        states={
            COMPLAINT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_complaint)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
