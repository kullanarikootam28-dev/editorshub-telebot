import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = None


def start_scheduler(application):
    global scheduler

    try:
        # ✅ CRITICAL: use Telegram application's running event loop
        loop = application.bot.loop

        scheduler = AsyncIOScheduler(event_loop=loop)

        # =========================
        # ADD YOUR JOBS HERE
        # =========================

        # Example safe job (keeps scheduler alive)
        scheduler.add_job(dummy_job, "interval", minutes=10)

        # =========================

        scheduler.start()

        logger.info("✅ Scheduler started with correct event loop")

    except Exception as e:
        logger.error(f"❌ Scheduler failed to start: {e}")


# =========================
# SAMPLE SAFE JOB
# =========================
async def dummy_job():
    try:
        logger.info("⏱ Scheduler heartbeat running...")
    except Exception as e:
        logger.error(f"Dummy job error: {e}")
