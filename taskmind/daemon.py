"""Main daemon loop - orchestrates capture at intervals."""
import os
import sys
import time
import signal
import logging
from datetime import datetime
from taskmind.config import load_config, PID_FILE, LOG_FILE, ensure_dirs
from taskmind.database import init_db, insert_activity
from taskmind.capture.window_tracker import get_active_window
from taskmind.capture.idle_detector import is_idle
from taskmind.processing.classifier import classify

logger = logging.getLogger("taskmind")
_running = True


def _setup_logging():
    ensure_dirs()
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _write_pid():
    ensure_dirs()
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_pid():
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def _signal_handler(sig, frame):
    global _running
    _running = False


def is_daemon_running():
    """Check if daemon is currently running."""
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # Check if process exists
        return True
    except (OSError, ValueError):
        _remove_pid()
        return False


def run_daemon():
    """Main daemon entry point."""
    global _running

    if is_daemon_running():
        print("TaskMind daemon is already running.")
        sys.exit(1)

    _setup_logging()
    init_db()
    _write_pid()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    config = load_config()
    interval = config["general"]["tracking_interval_seconds"]
    idle_threshold = config["general"]["idle_threshold_minutes"]
    blacklisted_apps = [a.lower() for a in config["tracking"]["blacklisted_apps"]]

    logger.info("TaskMind daemon started (PID %d, interval %ds)", os.getpid(), interval)
    print("TaskMind daemon started (PID {})".format(os.getpid()))

    try:
        from taskmind.utils.scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        logger.info("Scheduler started (recap, reminders)")
    except Exception as e:
        logger.warning("Scheduler failed to start: %s", e)

    try:
        while _running:
            try:
                timestamp = datetime.now().isoformat()
                idle = is_idle(idle_threshold)

                if idle:
                    insert_activity(timestamp, "", "", "", "", interval, is_idle=True)
                else:
                    window = get_active_window()
                    app = window["app_name"].lower()

                    # Skip blacklisted apps
                    if app in blacklisted_apps:
                        time.sleep(interval)
                        continue

                    project = classify(window["window_title"], window["app_name"], window["window_class"])
                    insert_activity(
                        timestamp,
                        window["window_title"],
                        window["app_name"],
                        window["window_class"],
                        project,
                        interval,
                        is_idle=False,
                    )
            except Exception as e:
                logger.error("Capture error: %s", e)

            time.sleep(interval)
    finally:
        try:
            from taskmind.utils.scheduler import stop_scheduler
            stop_scheduler()
        except Exception:
            pass
        _remove_pid()
        logger.info("TaskMind daemon stopped.")
        print("TaskMind daemon stopped.")
