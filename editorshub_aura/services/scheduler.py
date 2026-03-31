import datetime
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from database.sheets import get_all_records, update_order_status, update_editor_aura
from services.aura import calculate_review_points

logger = logging.getLogger(__name__)


async def check_submissions(app: Application):
    """
    Auto-approves orders that have been in 'Submitted for Review' for over 24 hours.
    Awards the editor 5-star aura points on auto-approval.
    """
    logger.info("Scheduler: running auto-approve check...")

    orders = get_all_records("Orders")
    now = datetime.datetime.now()

    for order in orders:
        if order.get("Status") != "Submitted for Review":
            continue

        submission_date_str = order.get("SubmissionDate") or order.get("UpdatedAt") or order.get("CreatedAt", "")
        if not submission_date_str:
            continue

        try:
            submitted_time = datetime.datetime.strptime(
                str(submission_date_str).strip(), "%Y-%m-%d %H:%M"
            )
        except ValueError:
            try:
                submitted_time = datetime.datetime.strptime(
                    str(submission_date_str).strip(), "%Y-%m-%d %H:%M:%S"
                )
            except ValueError:
                logger.warning(
                    f"Could not parse submission date '{submission_date_str}' for order {order.get('OrderID')}. Skipping."
                )
                continue

        if (now - submitted_time) < datetime.timedelta(hours=24):
            continue

        order_id = order.get("OrderID")
        editor_id = order.get("SelectedEditor")

        logger.info(f"Auto-approving order {order_id} (submitted >24h ago).")
        update_order_status(order_id, "Completed")

        if editor_id:
            points = calculate_review_points("completed") + calculate_review_points("5_star")
            update_editor_aura(editor_id, points)
            logger.info(f"Awarded {points} aura to editor {editor_id} for auto-approved order {order_id}.")

            try:
                await app.bot.send_message(
                    chat_id=editor_id,
                    text=(
                        f"✅ <b>Order {order_id} Auto-Approved!</b>\n\n"
                        f"The client did not respond within 24 hours, so your submission has been automatically approved.\n"
                        f"You've earned <b>{points} Aura points</b>. Great work!"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Could not notify editor {editor_id}: {e}")

        client_id = order.get("Client")
        if client_id:
            try:
                await app.bot.send_message(
                    chat_id=client_id,
                    text=(
                        f"ℹ️ <b>Order {order_id} Auto-Completed</b>\n\n"
                        f"Your order was auto-approved after 24 hours without a response. "
                        f"If you have any concerns, please contact support."
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Could not notify client {client_id}: {e}")


def start_scheduler(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_submissions, "interval", minutes=60, args=[app])
    scheduler.start()
    logger.info("Scheduler started — auto-approve check runs every 60 minutes.")
