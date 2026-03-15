from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from database.sheets import get_order

WAIT_MESSAGE = 1

def get_relay_keyboard(order_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💬 Send Message / Reply", callback_data=f"relay_start|{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def relay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    order_id = query.data.split('|')[1]
    context.user_data['relay_order_id'] = order_id
    
    await query.message.reply_text(f"Type your message for Order {order_id}. It will be sent anonymously.")
    return WAIT_MESSAGE

async def relay_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get('relay_order_id')
    user_id = str(update.message.from_user.id)
    text = update.message.text
    
    order = get_order(order_id)
    if not order:
        await update.message.reply_text("Order not found.")
        return ConversationHandler.END
        
    client_id = order.get('Client')
    editor_id = order.get('SelectedEditor')
    
    if user_id == client_id:
        target_id = editor_id
        prefix = f"👤 *Message from Client (Order {order_id})*\n\n"
    elif user_id == editor_id:
        target_id = client_id
        prefix = f"✂️ *Message from Editor (Order {order_id})*\n\n"
    else:
        await update.message.reply_text("You are not authorized to send messages for this order.")
        return ConversationHandler.END
        
    if not target_id:
        await update.message.reply_text("The other party is not assigned yet.")
        return ConversationHandler.END

    # Send block to target
    await context.bot.send_message(
        chat_id=target_id,
        text=prefix + text,
        parse_mode='Markdown',
        reply_markup=get_relay_keyboard(order_id)
    )
    
    await update.message.reply_text("✅ Message sent securely!")
    return ConversationHandler.END

async def cancel_relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Messaging canceled.")
    return ConversationHandler.END

def get_relay_conv_handler():
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(relay_start, pattern=r'^relay_start\|')],
        states={
            WAIT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, relay_receive)]
        },
        fallbacks=[CommandHandler('cancel', cancel_relay)]
    )
