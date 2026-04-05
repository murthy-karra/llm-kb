"""Background worker process.

Handles:
  1. Scan polling — checks GuardDuty tags on quarantined files every 10s
  2. Job execution — picks up pending compile/lint jobs from wiki_jobs table

Run as: uv run python -m app.worker
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, init_db
from app.core.scan_worker import process_pending_scans
import app.models  # noqa: F401 — ensure all models are registered with SQLAlchemy
from app.models.wiki_job import WikiJob

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("worker")

SCAN_POLL_INTERVAL = 10
JOB_POLL_INTERVAL = 3


async def pick_job(db: AsyncSession) -> WikiJob | None:
    """Atomically claim a pending job using SELECT FOR UPDATE SKIP LOCKED."""
    result = await db.execute(
        select(WikiJob)
        .where(WikiJob.status == "pending")
        .order_by(WikiJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()
    return job


async def execute_job(job: WikiJob) -> None:
    """Execute a single job. Updates status and result in the DB."""
    logger.info("Starting job %s: %s for wiki %s", job.id, job.job_type, job.wiki_id)

    async with async_session() as db:
        # Re-fetch job within this session
        result = await db.execute(select(WikiJob).where(WikiJob.id == job.id))
        job = result.scalar_one()

        async def update_progress(current, total, message):
            """Write progress to the job row so the frontend can poll it."""
            job.result = {
                **(job.result or {}),
                "progress": {
                    "current": current,
                    "total": total,
                    "message": message,
                },
            }
            await db.commit()

        try:
            if job.job_type in ("compile", "full_rebuild"):
                from app.compilation.wiki_compiler import compile_wiki_scoped
                full = job.job_type == "full_rebuild"
                articles, costs = await compile_wiki_scoped(
                    job.wiki_id, db, full_rebuild=full, on_progress=update_progress,
                )
                job.result = {
                    **(job.result or {}),
                    "articles_written": len(articles),
                    "articles": articles,
                    "usage": costs.to_dict(),
                    "progress": {"current": len(articles), "total": len(articles), "message": "Complete"},
                }
                job.status = "complete"

            elif job.job_type == "lint":
                from app.compilation.wiki_compiler import lint_wiki_scoped
                report, costs = await lint_wiki_scoped(
                    job.wiki_id, db, on_progress=update_progress,
                )
                job.result = {
                    **(job.result or {}),
                    "report": report,
                    "usage": costs.to_dict(),
                    "progress": {"current": 1, "total": 1, "message": "Complete"},
                }
                job.status = "complete"

            else:
                job.status = "failed"
                job.error = f"Unknown job type: {job.job_type}"

        except Exception as e:
            logger.exception("Job %s failed", job.id)
            job.status = "failed"
            job.error = str(e)

        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("Job %s finished: %s", job.id, job.status)


async def job_loop():
    """Poll for pending jobs and execute them."""
    logger.info("Job worker started (polling every %ds)", JOB_POLL_INTERVAL)
    while True:
        try:
            async with async_session() as db:
                job = await pick_job(db)

            if job:
                await execute_job(job)
            else:
                await asyncio.sleep(JOB_POLL_INTERVAL)
        except Exception:
            logger.exception("Job loop error")
            await asyncio.sleep(JOB_POLL_INTERVAL)


async def scan_loop():
    """Poll for pending scans."""
    logger.info("Scan worker started (polling every %ds)", SCAN_POLL_INTERVAL)
    while True:
        try:
            await process_pending_scans()
        except Exception:
            logger.exception("Scan worker error")
        await asyncio.sleep(SCAN_POLL_INTERVAL)


async def main():
    logger.info("Worker starting up...")
    await init_db()

    # Run both loops concurrently
    await asyncio.gather(
        scan_loop(),
        job_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
