import os
import sys
import tempfile
import threading
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from services.ingestion_service import run_weather_ingestion
from services.sachet_ingestion import fetch_and_store_sachet_alerts

logger = logging.getLogger("weather_scheduler")

_scheduler = None
_lock_file_fp = None
_initial_run_executed = False


def acquire_process_lock(lock_name="weather_platform_scheduler.lock"):
    """
    Acquire a cross-process file lock so only ONE Gunicorn worker or Flask process
    initializes the background scheduler and triggers the initial weather ingestion run.
    """
    global _lock_file_fp
    if _lock_file_fp is not None:
        return True

    lock_path = os.path.join(tempfile.gettempdir(), lock_name)
    try:
        fp = open(lock_path, "a+b")
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_file_fp = fp
        return True
    except (IOError, OSError):
        if 'fp' in locals() and fp:
            try:
                fp.close()
            except Exception:
                pass
        return False


def _run_initial_ingestion():
    """
    Background worker thread function to execute ONE initial weather ingestion run immediately
    upon application startup without blocking Flask or Gunicorn.
    """
    logger.info("Initial weather ingestion started")
    try:
        summary = run_weather_ingestion()
        if summary and (summary.get("status") == "success" or summary.get("success_count", 0) > 0):
            logger.info("Initial weather ingestion completed")
        else:
            reason = summary.get("message", "No records ingested") if summary else "Unknown response"
            logger.warning("Initial weather ingestion completed with warnings: %s", reason)
    except Exception as e:
        logger.error("Initial weather ingestion failed: %s", str(e))


def init_scheduler(app=None):
    """
    Initialize and start background periodic weather & SACHET RSS ingestion scheduler.
    Uses APScheduler BackgroundScheduler (15-minute interval).
    Safe for Render/Gunicorn multi-worker deployments and Flask debug reloader.
    """
    global _scheduler, _initial_run_executed

    # Handle Flask debug reloader (prevent running in master reloader process)
    is_reloader_active = os.environ.get("WERKZEUG_RUN_MAIN") is not None
    is_reloader_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if is_reloader_active and not is_reloader_worker:
        logger.info("Skipping background scheduler initialization in Flask master reloader process.")
        return

    # Cross-process lock for Gunicorn multi-worker safety
    if not acquire_process_lock():
        logger.info("Background scheduler lock already acquired by another process/worker. Skipping.")
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

        # Trigger ONE initial weather ingestion run immediately in background daemon thread
        if not _initial_run_executed:
            _initial_run_executed = True
            initial_thread = threading.Thread(
                target=_run_initial_ingestion,
                daemon=True,
                name="InitialWeatherIngestionThread"
            )
            initial_thread.start()

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
