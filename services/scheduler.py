import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from services.ingestion_service import run_weather_ingestion
from services.sachet_ingestion import fetch_and_store_sachet_alerts

logger = logging.getLogger("weather_scheduler")

_scheduler = None


def init_scheduler(app=None):
    """
    Initialize and start background periodic weather & SACHET RSS ingestion scheduler.
    Uses APScheduler BackgroundScheduler (15-minute interval).
    Guarantees single startup under Flask debug reloader mode.
    """
    global _scheduler

    # When Flask debug reloader is enabled (app.run(debug=True)), Werkzeug spawns two processes:
    # 1. Master reloader process (WERKZEUG_RUN_MAIN is not set)
    # 2. Child worker process (WERKZEUG_RUN_MAIN is 'true')
    # Initialize the scheduler ONLY in the worker process (or when reloader is not active).
    is_reloader_active = os.environ.get("WERKZEUG_RUN_MAIN") is not None
    is_reloader_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if is_reloader_active and not is_reloader_worker:
        logger.info("Skipping background scheduler initialization in Flask master reloader process.")
        return

    if _scheduler is not None and _scheduler.running:
        logger.info("Background Weather Ingestion Scheduler is already running.")
        return

    try:
        _scheduler = BackgroundScheduler(daemon=True)
        # Schedule periodic weather ingestion job every 15 minutes
        _scheduler.add_job(
            func=run_weather_ingestion,
            trigger="interval",
            minutes=15,
            id="periodic_weather_ingestion_job",
            name="Periodic 15-Minute Weather Ingestion",
            replace_existing=True
        )
        # Schedule periodic SACHET RSS disaster alert job every 15 minutes
        _scheduler.add_job(
            func=fetch_and_store_sachet_alerts,
            trigger="interval",
            minutes=15,
            id="periodic_sachet_rss_job",
            name="Periodic 15-Minute SACHET RSS Ingestion",
            replace_existing=True
        )
        _scheduler.start()
        logger.info("Background Weather & SACHET Ingestion Scheduler successfully started (Interval: 15 minutes).")
    except Exception as e:
        logger.error("Failed to initialize Background Weather Ingestion Scheduler: %s", str(e))


def get_scheduler_info():
    """Return status dictionary of the background scheduler."""
    global _scheduler
    is_running = _scheduler is not None and _scheduler.running
    return {
        "running": is_running,
        "interval_minutes": 15
    }
