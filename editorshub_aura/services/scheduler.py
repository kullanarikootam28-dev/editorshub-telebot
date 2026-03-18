from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

logger = logging.getLogger(__name__)

scheduler = None

def start_scheduler(app):
    global scheduler

    try:
        scheduler = AsyncIOScheduler()

        # Example job (safe placeholder)
        scheduler.add_job(dummy_job, "interval", minutes=10)

        scheduler.start()
        logger.info("Scheduler started successfully.")

    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")


async def dummy_job():
    # You can replace this later with real jobs
    pass
