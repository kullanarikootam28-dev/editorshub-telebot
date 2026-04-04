from html import escape
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import JOBS_CHANNEL_ID
from database.sheets import get_order, update_order_status, assign_editor_to_order, delete_applications_for_order, add_profit
from utils.keyboards import get_apply_job_keyboard, get_client_selection_keyboard
import datetime
import logging

logger = logging.getLogger(__name__)


# ── FIX: safe job-channel post builder ───────────────────────────────────────
# All user-supplied fields are HTML-escaped so Drive links / category text
# containing < > & cannot break parse_mode="HTML".
# Plain unicode emoji are used — no invisible/corrupted emoji bytes.
def _build_job_text(order_id: str, order: dict) -> str:
    def s(key, default="-"):
        return escape(str(order.get(key, default)))

    return (
        f"📋 <b>ORDER {order_id}</b>\n\n"
        f"🎬 Category: {s('Category')}\n"
        f"⏱ Duration: {s('Duration')}\n"
        f"📹 Videos: {s('Videos')}\n"
        f"💰 Editor Budget: ₹{s('EditorBudget')}\n"
        f"⏰ Deadline: {s('Deadline')}\n\n"
        f"📁 Raw Files: {s('RawFiles')}\n"
        f"🔗 Reference: {s('Reference')}"
    )


async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.auth import is_admin
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You are not authorized to view the dashboard.")
        return

    from utils.keyboards import get_admin_dashboard_keyboard
    dashboard_text = "📊 *ADMIN DASHBOARD*\n\nWelcome to your command center. Select an option below to view real-time metrics."
    await update.message.reply_text(dashboard_text, parse_mode="Markdown", reply_markup=get_admin_dashboard_keyboard())


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    from utils.auth import is_admin
    if not is_admin(update.effective_user.id):
        await query.answer("You are not authorized to perform this action.", show_alert=True)
        return

    await query.answer()

    data = query.data.split('|')
    action = data[0]

    if action == "dashboard":
        metric = data[1]
        from database.sheets import get_all_records
        from utils.keyboards import get_admin_dashboard_keyboard

        orders = get_all_records("Orders")
        text = "📊 *ADMIN DASHBOARD*\n\n"

        if metric == "revenue":
            total_revenue = sum([float(o.get("ClientBudget", 0)) for o in orders if str(o.get("ClientBudget", "0")).replace('.', '', 1).isdigit() and o.get("Status") in ["Completed", "Assigned", "Submitted for Review", "Revision Requested"]])
            total_margin = sum([float(o.get("PlatformProfit", 0)) for o in orders if str(o.get("PlatformProfit", "0")).replace('.', '', 1).isdigit() and o.get("Status") in ["Completed", "Assigned", "Submitted for Review", "Revision Requested"]])
            total_editor = sum([float(o.get("EditorBudget", 0)) for o in orders if str(o.get("EditorBudget", "0")).replace('.', '', 1).isdigit() and o.get("Status") in ["Completed", "Assigned", "Submitted for Review", "Revision Requested"]])
            text += f"*Financials:*\n• Money Collected: ₹{total_revenue:,.2f}\n• Platform Margin: ₹{total_margin:,.2f}\n• Editor Payouts: ₹{total_editor:,.2f}"

        elif metric == "status":
            status_counts = {}
            for o in orders:
                s = o.get("Status", "Unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            text += "*Order Statuses:*\n"
            for s, c in status_counts.items():
                text += f"• {s}: {c}\n"

        elif metric == "assignments":
            assignments = []
            from database.sheets import get_editor, get_client_record
            for o in orders:
                if o.get("SelectedEditor") and o.get("Status") not in ["Completed", "Canceled", "Denied"]:
                    editor_id = o.get("SelectedEditor")
                    client_id = o.get("Client")
                    editor = get_editor(editor_id)
                    client = get_client_record(client_id)
                    editor_username = editor.get("Username") if editor and editor.get("Username") else None
                    client_username = client.get("Username") if client and client.get("Username") else None
                    warn = ""
                    if not editor_username:
                        warn += " [Editor username missing]"
                    if not client_username:
                        warn += " [Client username missing]"
                    assignments.append(f"Editor @{editor_username if editor_username else editor_id} -> Client @{client_username if client_username else client_id} (Order {o['OrderID']}){warn}")
            text += "*Active Assignments:*\n"
            if assignments:
                for val in assignments[-15:]:
                    text += f"• {val}\n"
            else:
                text += "No active assignments."

        elif metric == "applications":
            from database.sheets import get_all_records as get_apps
            all_apps = get_apps("Applications")

            text += f"*Editor Applications ({len(all_apps)} total):*\n\n"

            if not all_apps:
                text += "✅ No applications yet!"
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_admin_dashboard_keyboard())
                return

            grouped = {}
            for app in all_apps:
                oid = app.get("OrderID", "?")
                if oid not in grouped:
                    grouped[oid] = []
                grouped[oid].append(app)

            app_buttons = []
            for oid, apps in list(grouped.items())[:15]:
                count = len(apps)
                app_buttons.append([InlineKeyboardButton(
                    f"📋 {oid} — {count} applicant{'s' if count > 1 else ''}",
                    callback_data=f"dashboard|view_applications|{oid}"
                )])
            app_buttons.append([InlineKeyboardButton("◀️ Back to Dashboard", callback_data="dashboard|refresh")])

            text += "Tap an order to review its applicants:"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(app_buttons))
            return

        elif metric == "view_applications":
            target_order_id = data[2]
            from database.sheets import get_applications
            apps = get_applications(target_order_id)

            text = f"👨‍💻 *Applicants for Order {target_order_id}*\n\n"

            if not apps:
                text += "No applicants for this order."
                back_btn = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="dashboard|applications")]])
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_btn)
                return

            app_buttons = []
            for app in apps:
                editor_id = app.get("Editor", "?")
                editor_username = app.get("Portfolio", editor_id)
                time_applied = app.get("AppliedAt", "")
                text += f"• @{editor_username} (ID: `{editor_id}`) — {time_applied}\n"
                app_buttons.append([
                    InlineKeyboardButton(f"✅ Assign @{editor_username}", callback_data=f"grant_assignment|{target_order_id}|{editor_id}")
                ])

            app_buttons.append([InlineKeyboardButton("◀️ Back to Applications", callback_data="dashboard|applications")])
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(app_buttons))
            return

        elif metric == "pending_orders":
            pending = [o for o in orders if o.get("Status") in ["Pending Approval", "Pending"]]
            text += f"*Pending Orders ({len(pending)} total):*\n\n"

            if not pending:
                text += "✅ No pending orders right now!"
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_admin_dashboard_keyboard())
                return

            order_buttons = []
            for o in pending[:20]:
                oid = o.get("OrderID", "?")
                cat = o.get("Category", "?")
                budget = o.get("ClientBudget", "?")
                order_buttons.append([InlineKeyboardButton(
                    f"📋 {oid} | {cat} | ₹{budget}",
                    callback_data=f"dashboard|view_order|{oid}"
                )])
            order_buttons.append([InlineKeyboardButton("◀️ Back to Dashboard", callback_data="dashboard|refresh")])

            text += "Tap any order below to review details and Approve / Deny:"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(order_buttons))
            return

        elif metric == "view_order":
            import asyncio
            order_id = data[2]
            order = await asyncio.to_thread(get_order, order_id)

            if not order:
                await query.edit_message_text(
                    f"⚠️ Order <code>{escape(order_id)}</code> not found in Sheets.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("◀️ Back to Pending Orders", callback_data="dashboard|pending_orders")
                    ]])
                )
                return

            view_text = (
                f"📋 <b>ORDER {escape(order_id)}</b>\n\n"
                f"👤 Client: <code>{escape(str(order.get('Client', '-')))}</code>\n"
                f"🎬 Category: {escape(str(order.get('Category', '-')))}\n"
                f"⏱ Duration: {escape(str(order.get('Duration', '-')))}\n"
                f"📹 Videos: {escape(str(order.get('Videos', '-')))}\n"
                f"💰 Client Budget: ₹{escape(str(order.get('ClientBudget', '-')))}\n"
                f"✂️ Editor Gets: ₹{escape(str(order.get('EditorBudget', '-')))}\n"
                f"📈 Platform Profit: ₹{escape(str(order.get('PlatformProfit', '-')))}\n"
                f"⏰ Deadline: {escape(str(order.get('Deadline', '-')))}\n"
                f"📁 Raw Files: {escape(str(order.get('RawFiles', '-')))}\n"
                f"🔗 Reference: {escape(str(order.get('Reference', '-')))}\n"
                f"📊 Status: <b>{escape(str(order.get('Status', '-')))}</b>"
            )

            action_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Order Granted", callback_data=f"approve_order|{order_id}")],
                [InlineKeyboardButton("❌ Deny Order", callback_data=f"deny_order|{order_id}")],
                [InlineKeyboardButton("◀️ Back to Pending Orders", callback_data="dashboard|pending_orders")]
            ])
            try:
                await query.edit_message_text(view_text, parse_mode="HTML", reply_markup=action_keyboard)
            except Exception as e:
                logger.error(f"view_order edit_message_text failed for {order_id}: {e}")
                await query.answer(f"Error displaying order: {e}", show_alert=True)
            return

        elif metric == "refresh":
            text += "Welcome to your command center. Select an option below to view real-time metrics."

        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_admin_dashboard_keyboard())

    elif action == "approve_order":
        import asyncio
        order_id = data[1]

        try:
            await query.edit_message_text(f"⏳ Processing Order <code>{escape(order_id)}</code>...", parse_mode="HTML")
        except Exception:
            pass

        try:
            order = await asyncio.to_thread(get_order, order_id)
        except Exception as e:
            logger.error(f"get_order failed for {order_id}: {e}")
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"❌ Failed to fetch Order <code>{escape(order_id)}</code> from database: {escape(str(e))}",
                parse_mode="HTML"
            )
            return

        if not order:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"❌ Order <code>{escape(order_id)}</code> not found in the database.",
                parse_mode="HTML"
            )
            return

        if order.get("Status") == "Approved":
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"ℹ️ Order <code>{escape(order_id)}</code> is already approved.",
                parse_mode="HTML"
            )
            return

        try:
            await asyncio.to_thread(update_order_status, order_id, "Approved")
        except Exception as e:
            logger.error(f"update_order_status failed for {order_id}: {e}")
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"❌ Failed to update order status: {escape(str(e))}",
                parse_mode="HTML"
            )
            return

        # ── Post to Jobs Channel ──────────────────────────────────────────────
        posted = False
        post_error = None
        if JOBS_CHANNEL_ID:
            # FIX: use the safe builder — no raw emoji bytes, all fields escaped
            job_text = _build_job_text(order_id, order)
            try:
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username
                msg = await context.bot.send_message(
                    chat_id=JOBS_CHANNEL_ID,
                    text=job_text,
                    parse_mode="HTML",
                    reply_markup=get_apply_job_keyboard(bot_username, order_id)
                )
                context.bot_data[f"job_msg_{order_id}"] = msg.message_id
                posted = True
                logger.info(f"Order {order_id} posted to Jobs Channel (msg_id={msg.message_id})")
            except Exception as e:
                post_error = str(e)
                logger.error(f"Failed to post order {order_id} to Jobs Channel: {e}")

        # ── Notify client ─────────────────────────────────────────────────────
        client_id = order.get("Client")
        if client_id:
            try:
                await context.bot.send_message(
                    chat_id=client_id,
                    text=(
                        f"✅ <b>Your Order {escape(order_id)} has been Approved!</b>\n\n"
                        f"We're now finding the best editor for your project.\n"
                        f"You'll be notified once an editor is assigned.\n\n"
                        f"Use /myorders to track your order anytime."
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not notify client {client_id}: {e}")

        # ── Final confirmation to admin ────────────────────────────────────────
        if posted:
            status_line = "✅ Job posted to Jobs Channel with APPLY button."
        elif post_error:
            status_line = f"⚠️ Could not post to Jobs Channel:\n<code>{escape(post_error[:200])}</code>"
        else:
            status_line = "⚠️ JOBS_CHANNEL_ID not configured — job not posted."

        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=f"✅ <b>Order {escape(order_id)} Approved!</b>\n\n{status_line}",
            parse_mode="HTML"
        )

    elif action == "deny_order":
        order_id = data[1]
        update_order_status(order_id, "Denied")
        await query.edit_message_text(f"Order {order_id} Denied.")

    elif action == "fwd_client":
        order_id = data[1]
        editor_id = data[2]

        from database.sheets import get_editor
        editor = get_editor(editor_id)

        aura = editor.get("Aura", "N/A") if editor else "N/A"
        rating = editor.get("Rating", "N/A") if editor else "N/A"
        portfolio = editor.get("Portfolio", None) if editor else None

        order = get_order(order_id)
        if order:
            client_id = order.get('Client')
            client_text = (
                f"👨‍💻 *An editor applied for your Order {order_id}*\n\n"
                f"Editor ID: `{editor_id}`\n"
                f"⚡ Aura: {aura}\n"
                f"⭐ Rating: {rating}\n"
            )
            if portfolio and portfolio.startswith("http"):
                portfolio_btn = [InlineKeyboardButton("🔗 View Portfolio", url=portfolio)]
            else:
                portfolio_btn = None

            keyboard_rows = []
            if portfolio_btn:
                keyboard_rows.append(portfolio_btn)
            keyboard_rows.append([InlineKeyboardButton("⭐ Select This Editor", callback_data=f"select_editor|{order_id}|{editor_id}")])
            client_markup = InlineKeyboardMarkup(keyboard_rows)

            try:
                await context.bot.send_message(
                    chat_id=client_id,
                    text=client_text,
                    parse_mode="Markdown",
                    reply_markup=client_markup
                )
                await query.edit_message_text(f"✅ Forwarded editor `{editor_id}` profile to client for Order {order_id}.", parse_mode="Markdown")
            except Exception as e:
                await query.edit_message_text(f"⚠️ Could not reach client {client_id}: {e}")
        else:
            await query.edit_message_text(f"Order {order_id} not found in Sheets.")

    elif action == "grant_assignment":
        order_id = data[1]
        editor_id = data[2]

        assign_editor_to_order(order_id, editor_id)
        delete_applications_for_order(order_id)

        await query.edit_message_text(f"Assigned {order_id} to Editor {editor_id}. Waiting for payment collection.")

        msg_id = context.bot_data.get(f"job_msg_{order_id}")
        if msg_id and JOBS_CHANNEL_ID:
            from database.sheets import get_editor
            editor = get_editor(editor_id)
            editor_username = editor.get("Username", str(editor_id)) if editor else str(editor_id)
            try:
                await context.bot.edit_message_text(
                    chat_id=JOBS_CHANNEL_ID,
                    message_id=msg_id,
                    text=f"✅ <b>{escape(order_id)} - Assigned to @{escape(editor_username)}</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to update jobs channel post for {order_id}: {e}")

        from utils.keyboards import get_payment_collection_keyboard
        order = get_order(order_id)
        if order:
            client_id = order.get('Client')
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Please collect ₹{order.get('ClientBudget')} from Client {client_id} before Editor starts.",
                reply_markup=get_payment_collection_keyboard(order_id, editor_id)
            )

    elif action == "payment_action":
        action_type = data[1]
        order_id = data[2]
        editor_id = data[3]

        if action_type == "collected":
            await query.edit_message_text(f"Payment collected for {order_id}. Notifying Editor {editor_id} to start.")

            msg_id = context.bot_data.get(f"job_msg_{order_id}")
            if msg_id and JOBS_CHANNEL_ID:
                try:
                    await context.bot.delete_message(chat_id=JOBS_CHANNEL_ID, message_id=msg_id)
                    await context.bot.send_message(chat_id=JOBS_CHANNEL_ID, text=f"ORDER {order_id} TAKEN")
                except Exception:
                    pass

            order = get_order(order_id)
            if order:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"Assignment Summary:\nClient: {order.get('Client')}\nEditor: {editor_id}\nEditor Payout: ₹{order.get('EditorBudget')}\nPlatform Profit: ₹{order.get('PlatformProfit')}"
                )

                from handlers.relay import get_relay_keyboard
                await context.bot.send_message(
                    chat_id=editor_id,
                    text=f"Payment Received! You can start ORDER {order_id}\nDeadline: {order.get('Deadline')}\nFiles: {order.get('RawFiles')}\nReference: {order.get('Reference')}",
                    reply_markup=get_relay_keyboard(order_id)
                )

                await context.bot.send_message(
                    chat_id=order.get('Client'),
                    text=f"Great news! Your Editor has been assigned and started work on Order {order_id}.",
                    reply_markup=get_relay_keyboard(order_id)
                )

        elif action_type == "not_yet":
            await query.answer("Still waiting for payment. Editor has not been notified.", show_alert=True)

        elif action_type == "canceled":
            await query.edit_message_text(f"Order {order_id} canceled due to non-payment.")
            update_order_status(order_id, "Canceled")

            await context.bot.send_message(chat_id=editor_id, text=f"Order {order_id} was canceled by the admin.")
            order = get_order(order_id)
            if order:
                await context.bot.send_message(chat_id=order.get('Client'), text=f"Order {order_id} was canceled.")

    elif action == "confirm_payment":
        order_id = data[1]
        order = get_order(order_id)

        if order:
            update_order_status(order_id, "Completed")

            profit_data = [
                order_id,
                order.get('Client'),
                order.get('SelectedEditor'),
                order.get('EditorBudget'),
                order.get('PlatformProfit'),
                datetime.datetime.now().strftime("%Y-%m-%d")
            ]
            add_profit(profit_data)

            await query.edit_message_text(f"Payment confirmed for {order_id}. Profit logged.")

            try:
                await context.bot.send_message(chat_id=order.get('SelectedEditor'), text=f"Payment released for Order {order_id}! Great job.")
            except Exception:
                pass
            try:
                await context.bot.send_message(chat_id=order.get('Client'), text=f"Order {order_id} is completed. Thank you!")
            except Exception:
                pass

    elif action == "eval_editor":
        sub_action = data[1]
        editor_id = data[2]

        temp = context.bot_data.get(f"temp_editor_{editor_id}", {})
        name = temp.get("name", "Unknown")
        username = temp.get("username", "Unknown")
        skill = temp.get("skill", "Unknown")
        software = temp.get("software", "Unknown")
        portfolio = temp.get("portfolio", "")
        test_link = temp.get("test_link", "")

        if sub_action == "approve":
            from database.sheets import add_editor
            from services.aura import get_aura_level

            editor_data = [
                editor_id,
                username,
                skill,
                portfolio,
                50,          # Starting Aura
                "5.0",       # Default Rating
                0,           # CompletedJobs
                0,           # ActiveJobs
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            ]
            try:
                add_editor(editor_data)
            except Exception as e:
                logger.error(f"Failed to add editor {editor_id} to sheet: {e}")
                await query.edit_message_text(f"⚠️ Could not save editor to database: {e}")
                return

            await query.edit_message_text(
                f"✅ Editor `{editor_id}` (@{username}) approved and added with 50 Aura.",
                parse_mode="Markdown"
            )

            # Generate invite link to Jobs Channel
            invite_link = None
            if JOBS_CHANNEL_ID:
                try:
                    invite = await context.bot.create_chat_invite_link(
                        chat_id=JOBS_CHANNEL_ID,
                        member_limit=1,
                        name=f"Invite for {name}"
                    )
                    invite_link = invite.invite_link
                except Exception as e:
                    logger.error(f"Could not generate invite link: {e}")

            editor_msg = (
                "🎉 *Congratulations!* Your test edit was approved!\n\n"
                "You have been granted *50 Aura* and are now an official Editor.\n\n"
            )
            if invite_link:
                editor_msg += f"🔗 *Join the Editors Hub here:* [Click to Join]({invite_link})\n\n"

            editor_msg += "You can view jobs in the channel and use commands like `/appliedjobs`."

            try:
                await context.bot.send_message(
                    chat_id=editor_id,
                    text=editor_msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            except Exception:
                pass

            # Welcome message in Jobs channel
            if JOBS_CHANNEL_ID:
                mention = f"@{username}" if username != "Unknown" else f"[{name}](tg://user?id={editor_id})"
                welcome_text = (
                    f"🎬 *Welcome our new Editor, {mention}!*\n\n"
                    f"🎯 *Skill:* {skill}\n"
                    f"⚡ *Starting Aura:* 50\n\n"
                    f"📌 *Please check out the Pinned Messages to learn about our rules, "
                    f"the Aura system, and how to use the Jobs workflow!*\n"
                    f"🏆 *Use /leaderboard to see top editors!*"
                )
                try:
                    await context.bot.send_message(
                        chat_id=JOBS_CHANNEL_ID,
                        text=welcome_text,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send welcome message: {e}")

        elif sub_action == "reject":
            await query.edit_message_text(f"❌ Rejected test submission for Editor `{editor_id}`.", parse_mode="Markdown")
            try:
                await context.bot.send_message(
                    chat_id=editor_id,
                    text="We appreciate your time, but unfortunately your test submission did not meet our current requirements. You may try again in the future."
                )
            except Exception:
                pass

        # Clean up temp data
        if f"temp_editor_{editor_id}" in context.bot_data:
            del context.bot_data[f"temp_editor_{editor_id}"]
