import asyncio
import datetime
import re
from html import escape

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config import ADMIN_ID
from services.revenue import calculate_margin
from utils.id_generator import generate_new_order_id
from database.sheets import (
    add_order,
    get_order,
    update_order_status,
    upsert_client,
    get_all_records,
)
from utils.keyboards import (
    get_admin_order_keyboard,
    get_order_category_keyboard,
    get_order_duration_keyboard,
    get_order_videos_keyboard,
    get_order_deadline_keyboard,
)

# ── Conversation states ────────────────────────────────────────────────────────
CATEGORY, DURATION, VIDEOS, DEADLINE, BUDGET, RAW_LINK, REF_LINK = range(7)

# Relay-inside-myorders state (offset to avoid collision)
RELAY_TYPING = 50

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cancel_keyboard():
    """Single-row keyboard with an ❌ Cancel button."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_order_flow")]
    ])


def _cancel_confirm_keyboard():
    """Yes/No keyboard used when user hits cancel during a loading operation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, cancel", callback_data="cancel_confirm|yes"),
            InlineKeyboardButton("🔙 No, continue", callback_data="cancel_confirm|no"),
        ]
    ])


async def _cancel_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the ❌ Cancel button pressed during any order step."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "❌ Order session cancelled. Use /order to start over."
    )
    return ConversationHandler.END


async def cancel_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Yes/No confirmation when user wants to cancel a loading session."""
    query = update.callback_query
    await query.answer()
    choice = query.data.split("|")[1]
    if choice == "yes":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ Session cancelled. Use /order to start a new one."
        )
        return ConversationHandler.END
    else:
        await query.edit_message_text(
            "▶️ Resuming… please send your response."
        )
        # Return to whatever state we were in (caller must handle)
        return None


# ── /myorders ─────────────────────────────────────────────────────────────────

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # Show a loading message so the user knows we're fetching
    loading_msg = await update.message.reply_text("⏳ Loading your orders…")

    all_orders = await asyncio.to_thread(get_all_records, "Orders")
    client_orders = [
        o for o in all_orders
        if str(o.get("Client", "")).strip() == user_id
    ]

    await loading_msg.delete()

    if not client_orders:
        await update.message.reply_text(
            "📭 You haven't placed any orders yet. Use /order to start!"
        )
        return

    text = f"📦 <b>Your Orders ({len(client_orders)} total)</b>\n\n"

    for o in sorted(client_orders, key=lambda x: x.get("CreatedAt", ""), reverse=True)[:10]:
        status = o.get("Status", "Unknown")
        order_id = escape(str(o.get("OrderID", "?")))

        if status in ["Pending Approval", "Pending"]:
            emoji = "⏳"
        elif status == "Posted to Channel":
            emoji = "📢"
        elif status in ["Editor Assigned", "Assigned"]:
            emoji = "🧑‍💻"
        elif status == "Completed":
            emoji = "✅"
        elif status in ["Denied", "Canceled", "Cancelled"]:
            emoji = "❌"
        else:
            emoji = "📝"

        text += (
            f"{emoji} <b>Order {order_id}</b> | {escape(o.get('Category', 'Video'))}\n"
            f"   Status: <i>{escape(status)}</i>\n"
            f"   Budget: ₹{escape(str(o.get('ClientBudget', '0')))}\n\n"
        )

    if len(client_orders) > 10:
        text += f"<i>…and {len(client_orders) - 10} older orders.</i>\n"

    # Build per-order 💬 Message Editor buttons (only for active/assigned orders)
    active_ids = [
        str(o.get("OrderID", ""))
        for o in client_orders
        if o.get("Status") in ["Assigned", "Editor Assigned", "Submitted for Review"]
    ]
    buttons = []
    for oid in active_ids[:5]:
        buttons.append(
            [InlineKeyboardButton(f"💬 Message Editor — {oid}", callback_data=f"relay_myorder|{oid}")]
        )

    markup = InlineKeyboardMarkup(buttons) if buttons else None
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)


# ── Relay from /myorders ──────────────────────────────────────────────────────

PRIVACY_NOTICE = (
    "📝 <b>Project Message Board — {order_id}</b>\n\n"
    "Type your message below. It will be delivered anonymously to the other party.\n\n"
    "⚠️ <b>Important Rules:</b>\n"
    "• <b>No private details</b> (phone numbers, email, social handles, payment info).\n"
    "• Sharing personal contact information will result in <b>immediate order cancellation</b> "
    "with <b>no refund</b>.\n"
    "• Keep all communication professional and project-related.\n\n"
    "<i>Use /cancel to exit the message board.</i>"
)


async def relay_myorder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point when client taps 💬 Message Editor from /myorders."""
    query = update.callback_query
    await query.answer()
    order_id = query.data.split("|")[1]
    context.user_data["relay_order_id"] = order_id

    await query.message.reply_text(
        PRIVACY_NOTICE.format(order_id=escape(order_id)),
        parse_mode="HTML",
        reply_markup=_cancel_keyboard(),
    )
    return RELAY_TYPING


async def relay_myorder_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the typed message and relays it to the editor via the bot."""
    order_id = context.user_data.get("relay_order_id")
    if not order_id:
        await update.message.reply_text("⚠️ Session expired. Use /myorders again.")
        return ConversationHandler.END

    user_id = str(update.message.from_user.id)
    raw_text = update.message.text or ""

    # Basic privacy filter — block obvious personal-info patterns
    blocked_patterns = [
        r"\b\d{10,}\b",                           # long digit strings (phone numbers)
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # emails
        r"(?i)(whatsapp|telegram\.me|t\.me|instagram|snapchat|facebook)\s*[:/]",
        r"(?i)(my number|call me|dm me|reach me)",
    ]
    for pat in blocked_patterns:
        if re.search(pat, raw_text):
            await update.message.reply_text(
                "🚫 <b>Message blocked.</b>\n\n"
                "Your message appears to contain private contact details, "
                "which violates our communication policy.\n\n"
                "Please rewrite your message without personal information.",
                parse_mode="HTML",
            )
            return RELAY_TYPING  # stay in state so they can retry

    order = await asyncio.to_thread(get_order, order_id)
    if not order:
        await update.message.reply_text("⚠️ Order not found.")
        return ConversationHandler.END

    client_id = str(order.get("Client", ""))
    editor_id = str(order.get("SelectedEditor", ""))

    if user_id == client_id:
        target_id = editor_id
        label = f"📨 Message from Client (Order {escape(order_id)})"
    elif user_id == editor_id:
        target_id = client_id
        label = f"✂️ Message from Editor (Order {escape(order_id)})"
    else:
        await update.message.reply_text("⛔ You are not a participant in this order.")
        return ConversationHandler.END

    if not target_id:
        await update.message.reply_text("⚠️ The other party has not been assigned yet.")
        return ConversationHandler.END

    msg_body = (
        f"<b>{label}</b>\n\n"
        f"{escape(raw_text)}\n\n"
        f"<i>Reply using the button below.</i>"
    )
    from handlers.relay import get_relay_keyboard
    try:
        await update.get_bot().send_message(
            chat_id=target_id,
            text=msg_body,
            parse_mode="HTML",
            reply_markup=get_relay_keyboard(order_id),
        )
        await update.message.reply_text("✅ Message sent securely!")
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not deliver message: {e}")

    return ConversationHandler.END


async def relay_myorder_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("relay_order_id", None)
    await update.message.reply_text("💬 Message board closed.")
    return ConversationHandler.END


# ── Order placement flow ──────────────────────────────────────────────────────

async def start_client_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to EditorsHub-AURA! Use /order to place a new editing request.\n"
        "Use /myorders to track your current orders."
    )


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "Let's place a new order.\nWhat type of project is this?"
    reply_markup = get_order_category_keyboard()
    # Attach cancel button alongside the category keyboard
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(
            msg, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    return CATEGORY


async def order_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split("|")
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text(
                "Please type your project category:", reply_markup=_cancel_keyboard()
            )
            return CATEGORY
        context.user_data["category"] = choice
        msg = update.callback_query.message
    else:
        context.user_data["category"] = update.message.text
        msg = update.message

    await msg.reply_text(
        "What is the expected duration of each video?",
        reply_markup=get_order_duration_keyboard(),
    )
    return DURATION


async def order_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split("|")
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text(
                "Please type the expected duration:", reply_markup=_cancel_keyboard()
            )
            return DURATION
        context.user_data["duration"] = choice
        msg = update.callback_query.message
    else:
        context.user_data["duration"] = update.message.text
        msg = update.message

    await msg.reply_text(
        "How many videos need editing?", reply_markup=get_order_videos_keyboard()
    )
    return VIDEOS


async def order_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split("|")
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text(
                "Please type the number of videos:", reply_markup=_cancel_keyboard()
            )
            return VIDEOS
        context.user_data["videos"] = choice
        msg = update.callback_query.message
    else:
        context.user_data["videos"] = update.message.text
        msg = update.message

    await msg.reply_text(
        "What is your deadline?", reply_markup=get_order_deadline_keyboard()
    )
    return DEADLINE


async def order_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        data = update.callback_query.data.split("|")
        choice = data[1]
        if choice == "Other":
            await update.callback_query.message.reply_text(
                "Please type your deadline:", reply_markup=_cancel_keyboard()
            )
            return DEADLINE
        context.user_data["deadline"] = choice
        msg = update.callback_query.message
    else:
        context.user_data["deadline"] = update.message.text
        msg = update.message

    await msg.reply_text(
        "What is your budget in INR? (numbers only, e.g. 2000)",
        reply_markup=_cancel_keyboard(),
    )
    return BUDGET


async def order_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    budget_text = update.message.text.replace(",", "").replace("₹", "").strip()
    try:
        budget = float(budget_text)
        context.user_data["client_budget"] = budget
        await update.message.reply_text(
            "Please provide the link to the Raw Footage (Google Drive only):",
            reply_markup=_cancel_keyboard(),
        )
        return RAW_LINK
    except ValueError:
        await update.message.reply_text(
            "Invalid budget. Please send a number only (e.g. 2000).",
            reply_markup=_cancel_keyboard(),
        )
        return BUDGET


async def order_raw_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not re.search(r"(drive\.google\.com|docs\.google\.com)", link):
        await update.message.reply_text(
            "Invalid link. Only Google Drive links are allowed. Please send a valid Google Drive link:",
            reply_markup=_cancel_keyboard(),
        )
        return RAW_LINK

    context.user_data["raw_link"] = link
    await update.message.reply_text(
        "Please provide a Reference Video link (or type 'None'):",
        reply_markup=_cancel_keyboard(),
    )
    return REF_LINK


async def order_ref_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ref_link"] = update.message.text
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or user_id

    # Show a loading message — Sheets write can be slow
    loading_msg = await update.message.reply_text(
        "⏳ Saving your order… please wait.",
        reply_markup=_cancel_confirm_keyboard(),
    )

    order_id = generate_new_order_id()
    client_budget = context.user_data["client_budget"]
    editor_budget, platform_profit = calculate_margin(client_budget)

    order_data = [
        order_id,
        user_id,
        context.user_data["category"],
        context.user_data["duration"],
        context.user_data["videos"],
        client_budget,
        editor_budget,
        platform_profit,
        context.user_data["deadline"],
        context.user_data["raw_link"],
        context.user_data["ref_link"],
        "Pending Approval",
        "",
        "Pending",
        "None",
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ]

    try:
        await asyncio.to_thread(add_order, order_data)
    except Exception as e:
        await loading_msg.delete()
        await update.message.reply_text(
            f"⚠️ Could not save your order right now.\n"
            f"Please try again in a few minutes or contact the admin.\n\n(Error: {e})"
        )
        return ConversationHandler.END

    await asyncio.to_thread(upsert_client, user_id, username)
    await loading_msg.delete()

    await update.message.reply_text(
        f"✅ Thank you! Your order `{order_id}` has been submitted for admin review.\n"
        f"You'll be notified once it's approved.",
        parse_mode="Markdown",
    )

    if ADMIN_ID:
        admin_text = (
            f"📋 *NEW ORDER REQUEST*\n\n"
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
                parse_mode="Markdown",
                reply_markup=get_admin_order_keyboard(order_id),
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"Failed to notify admin for order {order_id}: {e}"
            )

    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Order cancelled. Use /order to start over.")
    return ConversationHandler.END


# ── Conversation handler builders ─────────────────────────────────────────────

def get_order_conv_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("order", start_order),
            CallbackQueryHandler(start_order, pattern="^start_order_flow$"),
        ],
        states={
            CATEGORY: [
                CallbackQueryHandler(order_category, pattern=r"^category\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_category),
            ],
            DURATION: [
                CallbackQueryHandler(order_duration, pattern=r"^duration\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_duration),
            ],
            VIDEOS: [
                CallbackQueryHandler(order_videos, pattern=r"^videos\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_videos),
            ],
            DEADLINE: [
                CallbackQueryHandler(order_deadline, pattern=r"^deadline\|"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_deadline),
            ],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_budget)],
            RAW_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_raw_link)],
            REF_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_ref_link)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_order),
            # ❌ Cancel inline button
            CallbackQueryHandler(_cancel_button_handler, pattern="^cancel_order_flow$"),
            # Yes/No confirmation for long-loading cancels
            CallbackQueryHandler(cancel_confirm_handler, pattern="^cancel_confirm\\|"),
        ],
        allow_reentry=True,
    )


def get_relay_myorder_handler():
    """ConversationHandler for the inline message board in /myorders."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(relay_myorder_start, pattern=r"^relay_myorder\|"),
        ],
        states={
            RELAY_TYPING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, relay_myorder_send),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", relay_myorder_cancel),
            CallbackQueryHandler(_cancel_button_handler, pattern="^cancel_order_flow$"),
        ],
        allow_reentry=True,
    )


# ── client_editor_selection & client_revision_decision (unchanged logic) ──────

async def client_editor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action = data[0]

    if action == "select_editor":
        order_id = data[1]
        editor_id = data[2]
        await query.edit_message_text(
            f"You selected editor {editor_id}. Waiting for admin permission to assign."
        )
        if ADMIN_ID:
            from utils.keyboards import get_admin_grant_assignment_keyboard
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Client selected Editor {editor_id} for Order {order_id}. Grant permission?",
                reply_markup=get_admin_grant_assignment_keyboard(order_id, editor_id),
            )


async def client_revision_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action = data[0]
    order_id = data[1]

    if action == "req_revision":
        await query.edit_message_text(
            f"You requested a revision for Order {order_id}. The editor has been notified via admin."
        )
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"Revision requested by client for Order {order_id}. Please forward instructions to the editor.",
            )
            update_order_status(order_id, "Revision Requested")

    elif action == "rate":
        stars = data[2]
        await query.edit_message_text(
            f"Thank you for rating Order {order_id} with {stars} Stars!"
        )
        order = get_order(order_id)
        if order:
            editor_id = order.get("SelectedEditor")
            from database.sheets import update_editor_aura
            from services.aura import calculate_review_points

            update_editor_aura(editor_id, calculate_review_points("completed"))
            if stars == "5":
                update_editor_aura(editor_id, calculate_review_points("5_star"))
            update_order_status(order_id, "Completed")

            if ADMIN_ID:
                from utils.keyboards import get_payment_confirm_keyboard
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"Client rated {stars} stars for Order {order_id}.\nConfirm payment release to editor?",
                    reply_markup=get_payment_confirm_keyboard(order_id),
                )
