import asyncio
import re
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters,
)

from config import ADMIN_ID
from database.sheets import get_order, log_moderation_event
from services.moderator import moderate, REDIRECT_MESSAGE

WAIT_MESSAGE = 1

PRIVACY_NOTICE = (
    "📝 <b>Project Message Board — {order_id}</b>\n\n"
    "Type your message below. It will be delivered anonymously to the other party.\n\n"
    "⚠️ <b>Rules — read carefully:</b>\n"
    "• <b>No private details</b> (phone numbers, email, social handles, payment info).\n"
    "• Sharing personal contact information will result in <b>immediate order cancellation</b> "
    "with <b>no refund</b>.\n"
    "• Keep all communication professional and project-related only.\n\n"
    "<i>Use /cancel or the button below to exit.</i>"
)

# Hard-coded privacy patterns (fast, free pre-filter before AI check)
_PRIVACY_PATTERNS = [
    r"\b\d{10,}\b",
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    r"(?i)(whatsapp|telegram\.me|t\.me|instagram|snapchat|facebook)\s*[:/]",
    r"(?i)(my number|call me|dm me|reach me|contact me outside)",
]

PRIVACY_BLOCKED_MSG = (
    "🚫 <b>Message Blocked — Private Info Detected</b>\n\n"
    "Your message appears to contain personal contact details "
    "(phone numbers, email addresses, or social media handles).\n\n"
    "This violates our policy. All communication must stay within this message board.\n"
    "<i>Please rewrite your message without personal information.</i>"
)


def get_relay_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Send Message / Reply", callback_data=f"relay_start|{order_id}")]
    ])


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_relay_flow")]
    ])


async def relay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = query.data.split("|")[1]
    context.user_data["relay_order_id"] = order_id
    await query.message.reply_text(
        PRIVACY_NOTICE.format(order_id=escape(order_id)),
        parse_mode="HTML",
        reply_markup=_cancel_keyboard(),
    )
    return WAIT_MESSAGE


async def relay_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("relay_order_id")
    if not order_id:
        await update.message.reply_text("⚠️ Session expired. Tap the message button again.")
        return ConversationHandler.END

    user = update.message.from_user
    user_id = str(user.id)
    username = user.username or str(user.id)
    raw_text = update.message.text or ""

    # ── Step 1: Fast privacy pre-filter (no API call needed) ──────────────────
    for pat in _PRIVACY_PATTERNS:
        if re.search(pat, raw_text):
            await update.message.reply_text(PRIVACY_BLOCKED_MSG, parse_mode="HTML", reply_markup=_cancel_keyboard())
            await asyncio.to_thread(
                log_moderation_event,
                user_id, username, raw_text,
                "Private Contact Info", "relay", "Blocked",
            )
            if ADMIN_ID:
                await _notify_admin(context, user_id, username, raw_text, "Private Contact Info", order_id)
            return WAIT_MESSAGE

    # ── Step 2: AI Moderation check ───────────────────────────────────────────
    loading = await update.message.reply_text("⏳ Sending…")
    mod_result = await moderate(raw_text)
    await loading.delete()

    if mod_result["flagged"]:
        reason = mod_result["reason"]
        await update.message.reply_text(REDIRECT_MESSAGE, parse_mode="HTML")
        await asyncio.to_thread(
            log_moderation_event,
            user_id, username, raw_text,
            reason, "relay", "Blocked + Redirected",
        )
        if ADMIN_ID:
            await _notify_admin(context, user_id, username, raw_text, reason, order_id)
        return WAIT_MESSAGE  # stay in state — don't end session, user can retry with clean message

    # ── Step 3: Look up order and route message ───────────────────────────────
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
        await update.message.reply_text("⚠️ The other party is not assigned yet.")
        return ConversationHandler.END

    msg_body = (
        f"<b>{label}</b>\n\n"
        f"{escape(raw_text)}\n\n"
        f"<i>Reply using the button below.</i>"
    )
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


async def _notify_admin(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    username: str,
    message_text: str,
    reason: str,
    order_id: str,
):
    """Send admin an alert with flagged message details."""
    if not ADMIN_ID:
        return
    try:
        alert = (
            f"🚨 <b>AI Moderation Alert</b>\n\n"
            f"👤 User: @{escape(username)} (<code>{user_id}</code>)\n"
            f"📦 Order: <code>{escape(order_id)}</code>\n"
            f"🏷 Reason: <b>{escape(reason)}</b>\n\n"
            f"📝 <b>Flagged Message:</b>\n"
            f"<blockquote>{escape(message_text[:400])}</blockquote>\n\n"
            f"<i>Message was blocked and user was redirected to bot commands.</i>"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert, parse_mode="HTML")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Admin notification failed: {e}")


async def cancel_relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("relay_order_id", None)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("💬 Message board closed.")
    else:
        await update.message.reply_text("💬 Messaging cancelled.")
    return ConversationHandler.END


def get_relay_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(relay_start, pattern=r"^relay_start\|")],
        states={
            WAIT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, relay_receive)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_relay),
            CallbackQueryHandler(cancel_relay, pattern="^cancel_relay_flow$"),
        ],
        allow_reentry=True,
    )
