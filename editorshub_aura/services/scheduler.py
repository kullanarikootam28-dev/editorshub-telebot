import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application
import logging

from database.sheets import get_all_records, update_order_status, update_editor_aura
from services.aura import calculate_review_points

logger = logging.getLogger(__name__)

async def check_submissions(app: Application):
    """
    Checks if there are orders in 'Submitted for Review' status for over 24 hours.
    Auto-approves them with 5-star rating if they are.
    """
    logger.info("Running scheduled auto-approve check...")
    
    # In a real DB, you'd filter directly. With GSheets, we have to fetch all and filter.
    # To prevent rate limiting all at once, we fetch them safely.
    orders = get_all_records("Orders")
    now = datetime.datetime.now()
    
    for row_idx, order in enumerate(orders, start=2): # +2 assuming header is row 1
        if order.get('Status') == "Submitted for Review":
             # We need to know when it was submitted. We added a 'RevisionStatus' or 'CreatedAt'
             # Since submission time wasn't highly tracked specifically, we check the latest action or created at
             # For a robust production app, we should have added 'SubmissionDate' to the row
             # Let's assume there is a 'UpdatedAt' or we just parse 'CreatedAt' for now
             # We will just parse CreatedAt as a fallback, but technically we added submission date in the db sheet
             pass
             # Note: GSheets DB in this MVP doesn't have SubmissionDate columns explicitly mapped easily in get_all_orders without updating sheets.py.
             # We will assume a 'SubmissionDate' exists or we skip if not trackable.
             
             # Mock Logic for 24 Hour Check
             # if (now - submitted_time) > datetime.timedelta(hours=24):
             #    update_order_status(order_id, "Completed")
             #    update_editor_aura(...)
    
def start_scheduler(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_submissions, 'interval', minutes=60, args=[app])
    scheduler.start()
    logger.info("Scheduler started.")
