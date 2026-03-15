"""
Admin Post Flow — allows any authorized admin to post a project to the Jobs Channel.
Steps: Title → Description → Media (photo/video) → Budget → Deadline → Confirm & Post
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

from config import JOBS_CHANNEL_ID
from utils.auth import is_admin
from utils.keyboards import get_apply_job_keyboard
from utils.id_generator import generate_new_order_id

# ConversationHandler states
POST_TITLE, POST_DESC, POST_MEDIA, POST_BUDGET, POST_DEADLINE, POST_CONFIRM = range(6)

async def admin_post_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point triggered by the 'Post a Project' button in the dashboard."""
    query = update.callback_query
    await query.answer()
    
    if not is_admin(update.effective_user.id):
        await query.answer("⛔ Not authorized.", show_alert=True)
        return ConversationHandler.END
    
    context.user_data['admin_post'] = {}
    await query.message.reply_text(
        "📢 *Admin Project Post*\n\n"
        "Let's create a call-to-action post for editors in the Jobs Channel.\n\n"
        "Step 1 of 5\n*What is the project title?*\n(e.g., 'Instagram Reels Edit — Fashion Brand')",
        parse_mode="Markdown"
    )
    return POST_TITLE

async def post_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_post']['title'] = update.message.text.strip()
    await update.message.reply_text(
        "Step 2 of 5\n*Write a full project description:*\n"
        "Include all requirements, style references, and deliverables. Be detailed!",
        parse_mode="Markdown"
    )
    return POST_DESC

async def post_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_post']['description'] = update.message.text.strip()
    await update.message.reply_text(
        "Step 3 of 5\n*Send a media file* (photo or video) for reference.\n\n"
        "Or type `skip` if you don't have one.",
        parse_mode="Markdown"
    )
    return POST_MEDIA

async def post_media_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data['admin_post']['media_type'] = 'photo'
    context.user_data['admin_post']['media_id'] = photo.file_id
    await update.message.reply_text(
        "✅ Photo saved!\n\nStep 4 of 5\n*What is the budget for the editor? (in ₹)*",
        parse_mode="Markdown"
    )
    return POST_BUDGET

async def post_media_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    context.user_data['admin_post']['media_type'] = 'video'
    context.user_data['admin_post']['media_id'] = video.file_id
    await update.message.reply_text(
        "✅ Video saved!\n\nStep 4 of 5\n*What is the budget for the editor? (in ₹)*",
        parse_mode="Markdown"
    )
    return POST_BUDGET

async def post_media_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_post']['media_type'] = None
    context.user_data['admin_post']['media_id'] = None
    await update.message.reply_text(
        "Step 4 of 5\n*What is the budget for the editor? (in ₹)*",
        parse_mode="Markdown"
    )
    return POST_BUDGET

async def post_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.replace(',', '').replace('₹', '').strip()
    try:
        budget = float(raw)
    except ValueError:
        await update.message.reply_text("⚠️ Please send a number only, e.g., 2000")
        return POST_BUDGET
    
    context.user_data['admin_post']['budget'] = budget
    await update.message.reply_text(
        "Step 5 of 5\n*What is the deadline for this project?*\n(e.g., 24 Hours, 2 Days, 1 Week)",
        parse_mode="Markdown"
    )
    return POST_DEADLINE

async def post_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_post']['deadline'] = update.message.text.strip()
    data = context.user_data['admin_post']
    
    preview = (
        f"🎯 *PROJECT PREVIEW*\n\n"
        f"📌 *{data['title']}*\n\n"
        f"📝 {data['description']}\n\n"
        f"💰 Editor Budget: ₹{data['budget']}\n"
        f"⏰ Deadline: {data['deadline']}\n"
        f"📎 Media: {'Attached' if data.get('media_id') else 'None'}\n\n"
        f"Does this look right? Tap *Confirm & Post* to publish to the Jobs Channel!"
    )
    
    confirm_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm & Post to Jobs Channel", callback_data="confirm_admin_post")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_admin_post")]
    ])
    
    await update.message.reply_text(preview, parse_mode="Markdown", reply_markup=confirm_keyboard)
    return POST_CONFIRM

async def post_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_admin_post":
        await query.edit_message_text("❌ Post cancelled.")
        context.user_data.pop('admin_post', None)
        return ConversationHandler.END
    
    data = context.user_data.get('admin_post', {})
    order_id = generate_new_order_id()
    
    post_text = (
        f"🔥 *NEW PROJECT OPPORTUNITY*\n\n"
        f"📌 *{data['title']}*\n\n"
        f"📝 {data['description']}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Editor Budget:* ₹{data['budget']}\n"
        f"⏰ *Deadline:* {data['deadline']}\n"
        f"🆔 *Order ID:* {order_id}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 *Tap below to apply!*"
    )
    
    apply_markup = get_apply_job_keyboard(context.bot.username, order_id)
    
    try:
        if data.get('media_type') == 'photo':
            await context.bot.send_photo(
                chat_id=JOBS_CHANNEL_ID,
                photo=data['media_id'],
                caption=post_text,
                parse_mode="Markdown",
                reply_markup=apply_markup
            )
        elif data.get('media_type') == 'video':
            await context.bot.send_video(
                chat_id=JOBS_CHANNEL_ID,
                video=data['media_id'],
                caption=post_text,
                parse_mode="Markdown",
                reply_markup=apply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=JOBS_CHANNEL_ID,
                text=post_text,
                parse_mode="Markdown",
                reply_markup=apply_markup
            )
        
        # --- Save the order to Sheets so the ID is reserved ---
        try:
            from database.sheets import add_order
            import datetime as dt
            admin_id = str(update.effective_user.id)
            order_row = [
                order_id,
                admin_id,                                   # Client (posted by admin)
                data.get('title', 'Admin Post'),            # Category / title
                "-",                                        # Duration
                "-",                                        # Videos
                0,                                          # ClientBudget
                data['budget'],                             # EditorBudget
                0,                                          # PlatformProfit
                data['deadline'],                           # Deadline
                "-",                                        # RawFiles
                "-",                                        # Reference
                "Posted to Channel",                        # Status
                "",                                         # SelectedEditor
                "N/A",                                      # PaymentStatus
                "None",                                     # RevisionStatus
                dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # CreatedAt
            ]
            add_order(order_row)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to save admin post order {order_id} to Sheets: {e}")
        
        await query.edit_message_text(
            f"✅ *Project posted to Jobs Channel!*\nOrder ID: `{order_id}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.edit_message_text(f"⚠️ Failed to post: `{e}`", parse_mode="Markdown")
    
    context.user_data.pop('admin_post', None)
    return ConversationHandler.END

async def post_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('admin_post', None)
    await update.message.reply_text("❌ Admin post cancelled.")
    return ConversationHandler.END

def get_admin_post_handler():
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_post_entry, pattern='^admin_post_start$')
        ],
        states={
            POST_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_title)],
            POST_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, post_description)],
            POST_MEDIA: [
                MessageHandler(filters.PHOTO, post_media_photo),
                MessageHandler(filters.VIDEO, post_media_video),
                MessageHandler(filters.Regex(r'(?i)^skip$'), post_media_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, post_media_skip),
            ],
            POST_BUDGET:   [MessageHandler(filters.TEXT & ~filters.COMMAND, post_budget)],
            POST_DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_deadline)],
            POST_CONFIRM:  [CallbackQueryHandler(post_confirm, pattern='^(confirm|cancel)_admin_post$')],
        },
        fallbacks=[CommandHandler('cancel', post_cancel)],
        allow_reentry=True,
    )
