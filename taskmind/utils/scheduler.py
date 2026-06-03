"""Scheduler for daily recap and timesheet reminders."""
from apscheduler.schedulers.background import BackgroundScheduler
from taskmind.config import load_config
from taskmind.processing.recap import generate_recap
from taskmind.utils.notifications import notify


scheduler = BackgroundScheduler(daemon=True)


def _daily_recap_job():
    """Send daily recap notification."""
    recap = generate_recap()
    # Shorten for notification
    lines = recap.split("\n")
    short = "\n".join(lines[:8])
    notify("📋 Daily Recap", short)


def _timesheet_reminder_job():
    """Remind user to approve timesheet if not done."""
    from taskmind.database import get_total_tracked_today
    total = get_total_tracked_today()
    if total > 0:
        h, m = divmod(total // 60, 60)
        notify("⏰ Timesheet Reminder", "You tracked {}h {}m today.\nRun: taskmind timesheet".format(h, m))


def start_scheduler():
    """Start scheduled jobs based on config."""
    config = load_config()
    if not config.get("notifications", {}).get("enabled", True):
        return

    recap_time = config["general"].get("recap_time", "17:30")
    rh, rm = int(recap_time.split(":")[0]), int(recap_time.split(":")[1])

    # Daily recap at configured time
    if config.get("notifications", {}).get("daily_recap", True):
        scheduler.add_job(_daily_recap_job, "cron", hour=rh, minute=rm, id="daily_recap")

    # Timesheet reminder 30 min after recap
    if config.get("notifications", {}).get("timesheet_reminder", True):
        remind_h, remind_m = divmod(rh * 60 + rm + 30, 60)
        scheduler.add_job(_timesheet_reminder_job, "cron", hour=remind_h, minute=remind_m, id="timesheet_reminder")

    scheduler.start()


def stop_scheduler():
    """Shut down scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
