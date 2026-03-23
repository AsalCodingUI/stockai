"""APScheduler runner and lifecycle helpers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from stockai.scheduler import jobs

logger = logging.getLogger(__name__)

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
_scheduler: AsyncIOScheduler | None = None


def setup_scheduler() -> AsyncIOScheduler:
    """Configure scheduler and all recurring jobs."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone=JAKARTA_TZ)

    scheduler.add_job(
        jobs.morning_scan,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=45, timezone=JAKARTA_TZ),
        id="morning_scan",
        name="Morning Scan",
        replace_existing=True,
    )
    scheduler.add_job(
        jobs.midday_check,
        CronTrigger(day_of_week="mon-fri", hour=11, minute=30, timezone=JAKARTA_TZ),
        id="midday_check",
        name="Midday SL Monitor",
        replace_existing=True,
    )
    scheduler.add_job(
        jobs.closing_scan,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone=JAKARTA_TZ),
        id="closing_scan",
        name="Closing Scan",
        replace_existing=True,
    )
    scheduler.add_job(
        jobs.weekend_summary,
        CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=JAKARTA_TZ),
        id="weekend_summary",
        name="Weekend Summary",
        replace_existing=True,
    )
    _scheduler = scheduler
    return scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = setup_scheduler()
    if not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started")
    return _scheduler


def shutdown_scheduler(wait: bool = False) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=wait)
        logger.info("Scheduler stopped")


def scheduler_status() -> dict[str, Any]:
    scheduler = _scheduler
    if scheduler is None:
        return {"running": False, "jobs": []}
    job_rows = []
    now = datetime.now(JAKARTA_TZ)
    for job in scheduler.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        if next_run is None:
            next_run = getattr(job, "next_fire_time", None)
        if next_run is None:
            trigger = getattr(job, "trigger", None)
            try:
                next_run = trigger.get_next_fire_time(None, now) if trigger else None
            except Exception:
                next_run = None
        next_text = (
            next_run.astimezone(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M:%S WIB")
            if next_run
            else None
        )
        job_rows.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": next_text,
            }
        )
    return {
        "running": bool(scheduler.running),
        "jobs": job_rows,
        "timestamp": datetime.now(JAKARTA_TZ).strftime("%Y-%m-%d %H:%M:%S WIB"),
    }


async def run_job_now(job_id: str) -> dict[str, Any]:
    mapping = {
        "morning_scan": jobs.morning_scan,
        "midday_check": jobs.midday_check,
        "closing_scan": jobs.closing_scan,
        "weekend_summary": jobs.weekend_summary,
    }
    fn = mapping.get(job_id)
    if fn is None:
        raise ValueError(f"Unknown job id: {job_id}")
    result = await fn()
    return {"job": job_id, "result": result}


def run_forever() -> None:
    """Standalone scheduler loop for CLI `scheduler start`."""
    start_scheduler()
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        shutdown_scheduler(wait=False)
