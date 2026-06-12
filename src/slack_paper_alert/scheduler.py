from __future__ import annotations

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_settings
from .job import run_daily_job


def serve(hour: int = 9, minute: int = 0) -> None:
    settings = load_settings()
    scheduler = BlockingScheduler(timezone=settings.timezone)
    scheduler.add_job(
        run_daily_job,
        CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
        id="daily-paper-alert",
        replace_existing=True,
    )
    print(f"Scheduler started. Daily job time: {hour:02d}:{minute:02d} ({settings.timezone})")
    scheduler.start()

