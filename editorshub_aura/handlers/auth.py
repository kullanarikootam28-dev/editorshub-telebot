from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import SUPER_ADMIN_ID
from utils.auth import is_admin, add_admin, remove_admin

async def manage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for Super Admin to manage access via /manage <id>"""
    if str(update.effective_user.id) != str(SUPER_ADMIN_ID):
        await update.message.reply_text("⛔ Only the Super Admin can use this command.")
        return
        
    if not context.args:
        await update.message.reply_text("Usage: /manage <user_id>")
        return
        
    target_id = context.args[0]
    keyboard = [
        [InlineKeyboardButton("✅ Promote to Admin", callback_data=f"auth|promote|{target_id}")],
        [InlineKeyboardButton("❌ Remove Admin", callback_data=f"auth|demote|{target_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    current_status = "Admin" if is_admin(target_id) else "User"
    await update.message.reply_text(
        f"Manage User: `{target_id}`\nCurrent Status: **{current_status}**\n\nSelect an action:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def promote_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promotes the user whose message is replied to."""
    if str(update.effective_user.id) != str(SUPER_ADMIN_ID):
        return
        
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ You must reply to the user's message to promote them.")
        return
        
    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name
    
    if add_admin(target_id):
        await update.message.reply_text(f"✅ {target_name} (`{target_id}`) has been promoted to Admin.")
    else:
        await update.message.reply_text(f"ℹ️ {target_name} is already an Admin.")

async def demote_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Demotes the user whose message is replied to."""
    if str(update.effective_user.id) != str(SUPER_ADMIN_ID):
        return
        
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ You must reply to the user's message to demote them.")
        return
        
    target_id = update.message.reply_to_message.from_user.id
    target_name = update.message.reply_to_message.from_user.first_name
    
    if str(target_id) == str(SUPER_ADMIN_ID):
        await update.message.reply_text("⛔ You cannot demote the Super Admin.")
        return
        
    if remove_admin(target_id):
        await update.message.reply_text(f"❌ {target_name} (`{target_id}`) has been removed from Admins.")
    else:
        await update.message.reply_text(f"ℹ️ {target_name} is not currently an Admin.")

async def auth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Only super admin can click these buttons
    if str(update.effective_user.id) != str(SUPER_ADMIN_ID):
        await query.answer("⛔ Only the Super Admin can use these buttons.", show_alert=True)
        return
        
    await query.answer()
    data = query.data.split('|')
    action = data[1]
    target_id = data[2]
    
    if action == "promote":
        if add_admin(target_id):
            await query.edit_message_text(f"✅ User `{target_id}` promoted to Admin.", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"ℹ️ User `{target_id}` is already an Admin.", parse_mode="Markdown")
            
    elif action == "demote":
        if str(target_id) == str(SUPER_ADMIN_ID):
            await query.edit_message_text("⛔ Cannot demote Super Admin.")
            return
            
        if remove_admin(target_id):
            await query.edit_message_text(f"❌ User `{target_id}` removed from Admins.", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"ℹ️ User `{target_id}` is not an Admin.", parse_mode="Markdown")
