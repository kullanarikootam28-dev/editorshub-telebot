import datetime
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from config import ADMIN_ID
from services.revenue import calculate_margin
from utils.id_generator import generate_new_order_id
from database.sheets import add_order, get_order, update_order_status, upsert_client, get_all_records
from utils.keyboards import (
    get_admin_order_keyboard, get_order_category_keyboard,
    get_order_duration_keyboard, get_order_videos_keyboard,
    get_order_deadline_keyboard
)

CATEGORY, DURATION, VIDEOS, DEADLINE, BUDGET, RAW_LINK, REF_LINK = range(7)

async def start_client_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to EditorsHub-AURA! Use /order to place a new editing request.\nUse /myorders to track your current orders.")

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    all_orders = get_all_records("Orders")
    
    # Filter orders for this client. 
    # Note: Sheets auto-converts some IDs to int, so convert back to str for safe comparison.
    client_orders = [o for o in all_orders if str(o.get('Client', '')).strip() == user_id]
    
    if not client_orders:
        await update.message.reply_text("📦 You haven't placed any orders yet. Use /order to start!")
        return
        
    text = f"📦 <b>Your Orders ({len(client_orders)} total)</b>\n\n"
    
    for o in sorted(client_orders, key=lambda x: x.get('CreatedAt', ''), reverse=True)[:10]: # show latest 10
        status = o.get("Status", "Unknown")
        
        # Determine emoji based on status
        if status in ["Pending Approval", "Pending"]: emoji = "⏳"
        elif status == "Posted to Channel": emoji = "📢"
        elif status == "Editor Assigned": emoji = "👨‍💻"
        elif status == "Completed": emoji = "✅"
        elif status in ["Denied", "Canceled", "Cancelled"]: emoji = "❌"
        else: emoji = "🔖"

        text += (
            f"{emoji} <b>Order {o.get('OrderID')}</b> | {o.get('Category', 'Video')}\n"
            f"   Status: <i>{status}</i>\n"
            f"   Budget: ₹{o.get('ClientBudget', '0')}\n\n"
        )
        
    if len(client_orders) > 10:
        text += f"<i>...and {len(client_orders)-10} older orders.</i>"
        
    await update.message.reply_text(text, parse_mode="HTML")

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "Let's place a new order.\nWhat type of project is this?"
    reply_markup = get_order_category_keyboard()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    return CATEGORY

async def order_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split('|')
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text("Please type your project category:")
            return CATEGORY
        context.user_data['category'] = choice
        msg = update.callback_query.message
    else:
        context.user_data['category'] = update.message.text
        msg = update.message
        
    await msg.reply_text("What is the expected duration of each video?", reply_markup=get_order_duration_keyboard())
    return DURATION

async def order_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split('|')
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text("Please type the expected duration:")
            return DURATION
        context.user_data['duration'] = choice
        msg = update.callback_query.message
    else:
        context.user_data['duration'] = update.message.text
        msg = update.message
        
    await msg.reply_text("How many videos need editing?", reply_markup=get_order_videos_keyboard())
    return VIDEOS

async def order_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split('|')
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text("Please type the number of videos:")
            return VIDEOS
        context.user_data['videos'] = choice
        msg = update.callback_query.message
    else:
        context.user_data['videos'] = update.message.text
        msg = update.message
        
    await msg.reply_text("What is your deadline?", reply_markup=get_order_deadline_keyboard())
    return DEADLINE

async def order_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split('|')
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text("Please type your deadline:")
            return DEADLINE
        context.user_data['deadline'] = choice
        msg = update.callback_query.message
    else:
        context.user_data['deadline'] = update.message.text
        msg = update.message
        
    await msg.reply_text("What is your budget in INR? (Please enter numbers only, e.g., 2000)")
    return BUDGET

async def order_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget_text = update.message.text.replace(',', '').replace('₹', '').strip()
    try:
        budget = float(budget_text)
        context.user_data['client_budget'] = budget
        await update.message.reply_text("Please provide the link to the Raw Footage (Google Drive only):")
        return RAW_LINK
    except ValueError:
        await update.message.reply_text("Invalid budget. Please send a number only (e.g., 2000).")
        return BUDGET

async def order_raw_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not re.search(r'(drive\.google\.com|docs\.google\.com)', link):
        await update.message.reply_text("Invalid link. Only Google Drive links are allowed for raw footage. Please send a valid Google Drive link:")
        return RAW_LINK
        
    context.user_data['raw_link'] = link
    await update.message.reply_text("Please provide a Reference Video link (or type 'None'):")
    return REF_LINK

async def order_ref_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ref_link'] = update.message.text
    
    # Process the order
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or user_id
    
    order_id = generate_new_order_id()
    client_budget = context.user_data['client_budget']
    editor_budget, platform_profit = calculate_margin(client_budget)
    
    order_data = [
        order_id,
        user_id,                                    # Client
        context.user_data['category'],              # Category
        context.user_data['duration'],              # Duration
        context.user_data['videos'],                # Videos
        client_budget,                              # ClientBudget
        editor_budget,                              # EditorBudget
        platform_profit,                            # PlatformProfit
        context.user_data['deadline'],              # Deadline
        context.user_data['raw_link'],              # RawFiles
        context.user_data['ref_link'],              # Reference
        "Pending Approval",                         # Status
        "",                                         # SelectedEditor
        "Pending",                                  # PaymentStatus
        "None",                                     # RevisionStatus
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # CreatedAt
    ]
    
    # --- Save to Google Sheets (fail loudly so admin gets real errors) ---
    try:
        add_order(order_data)
    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Sorry, we could not save your order right now due to a system error.\n"
            f"Please try again in a few minutes or contact the admin.\n\n"
            f"(Error: {e})"
        )
        return ConversationHandler.END

    # --- Update / create the client record in Sheets ---
    upsert_client(user_id, username)

    await update.message.reply_text(
        f"✅ Thank you! Your order `{order_id}` has been submitted for admin review.\n"
        f"You'll be notified once it's approved.",
        parse_mode="Markdown"
    )
    
    # --- Notify admin ---
    if ADMIN_ID:
        admin_text = (
            f"🆕 *NEW ORDER REQUEST*\n\n"
            f"OrderID: `{order_id}`\n"
            f"Client: @{username} (`{user_id}`)\n"
            f"Category: {context.user_data['category']}\n"
            f"Duration: {context.user_data['duration']}\n"
            f"Videos: {context.user_data['videos']}\n"
            f"Budget: ₹{client_budget} → Editor gets ₹{editor_budget}\n"
            f"Deadline: {context.user_data['deadline']}\n"
            f"Raw Files: {context.user_data['raw_link']}\n"
            f"Reference: {context.user_data['ref_link']}\n"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode='Markdown',
                reply_markup=get_admin_order_keyboard(order_id)
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to notify admin for order {order_id}: {e}")
        
    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Order cancelled.")
    return ConversationHandler.END

def get_order_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler('order', start_order),
            CallbackQueryHandler(start_order, pattern='^start_order_flow$')
        ],
        states={
            CATEGORY: [
                CallbackQueryHandler(order_category, pattern=r'^category\|'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_category)
            ],
            DURATION: [
                CallbackQueryHandler(order_duration, pattern=r'^duration\|'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_duration)
            ],
            VIDEOS: [
                CallbackQueryHandler(order_videos, pattern=r'^videos\|'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_videos)
            ],
            DEADLINE: [
                CallbackQueryHandler(order_deadline, pattern=r'^deadline\|'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_deadline)
            ],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_budget)],
            RAW_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_raw_link)],
            REF_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_ref_link)],
        },
        fallbacks=[CommandHandler('cancel', cancel_order)]
    )

async def client_editor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('|')
    action = data[0]
    
    if action == "select_editor":
        order_id = data[1]
        editor_id = data[2]
        await query.edit_message_text(f"You selected editor {editor_id}. Waiting for admin permission to assign.")
        
        # Notify admin to grant assignment
        if ADMIN_ID:
            from utils.keyboards import get_admin_grant_assignment_keyboard
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Client selected Editor {editor_id} for Order {order_id}. Grant permission?",
                reply_markup=get_admin_grant_assignment_keyboard(order_id, editor_id)
            )

async def client_revision_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('|')
    action = data[0]
    order_id = data[1]
    
    if action == "req_revision":
        await query.edit_message_text(f"You requested a revision for Order {order_id}. The editor has been notified via admin.")
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Revision requested by client for Order {order_id}. Please forward instructions to the editor."
            )
            update_order_status(order_id, "Revision Requested")
            
    elif action == "rate":
        stars = data[2]
        await query.edit_message_text(f"Thank you for rating Order {order_id} with {stars} Stars!")
        
        # update aura
        order = get_order(order_id)
        if order:
            editor_id = order.get("SelectedEditor")
            from database.sheets import update_editor_aura
            from services.aura import calculate_review_points
            
            # +20 for completion
            update_editor_aura(editor_id, calculate_review_points('completed'))
            
            if stars == "5":
                update_editor_aura(editor_id, calculate_review_points('5_star'))
                
            update_order_status(order_id, "Completed")
            
            if ADMIN_ID:
                from utils.keyboards import get_payment_confirm_keyboard
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"Client rated {stars} stars for Order {order_id}.\nConfirm payment release to editor?",
                    reply_markup=get_payment_confirm_keyboard(order_id)
                )
