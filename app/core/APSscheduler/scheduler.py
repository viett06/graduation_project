from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.db.session import SessionLocal
from app.crawler.crawler_service import CrawlerService
import logging

logger = logging.getLogger(__name__)

# Async scheduler for FastAPI
scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")


async def crawl_job():
    """
    Scheduled task executed every 60 minutes via APScheduler.
    Iterates through all registered banks to update interest rate data.
    """
    db = SessionLocal()
    try:
        service = CrawlerService(db)
        logger.info("[Scheduler] Initiating automated crawl cycle for all banks...")

        results = await service.crawl_all_banks(admin_id=1)

        success_count = sum(1 for status in results.values() if status.get("status") == "success")
        fail_count = len(results) - success_count

        logger.info(
            f"[Scheduler] Cycle complete. Success: {success_count}, Failures: {fail_count}"
        )

    except Exception as e:
        logger.exception(f"[Scheduler] Critical failure in crawl_job: {str(e)}")

    finally:
        db.close()
        logger.info("[Scheduler] Database connection closed. Waiting for next interval")


def start_scheduler():
    """
    run job.
    """
    scheduler.add_job(
        crawl_job,
        IntervalTrigger(minutes=1),
        id="crawl_every_60_minutes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300
    )

    scheduler.start()

    logger.info("Scheduler started: crawl every 60 minutes.")


def stop_scheduler():
    scheduler.shutdown()
    logger.info("Scheduler stopped.")