import asyncio
import logging
from datetime import datetime, timezone, timedelta

from botocore.exceptions import ClientError
from sqlalchemy import select

from app.core.aws import get_s3_client
from app.core.config import settings
from app.core.database import async_session

logger = logging.getLogger(__name__)

SCAN_TIMEOUT_SECONDS = 10 * 60
POLL_INTERVAL_SECONDS = 10
GUARDDUTY_SCAN_STATUS_TAG = "GuardDutyMalwareScanStatus"
GUARDDUTY_THREAT_STATUS_TAG = "THREATS_FOUND"


async def process_pending_scans():
    """Check GuardDuty tags on all pending_scan files and transfer clean ones."""
    from app.models.wiki_file import WikiFile

    async with async_session() as db:
        result = await db.execute(
            select(WikiFile).where(
                WikiFile.status == "pending_scan",
                WikiFile.scan_started_at.isnot(None),
            )
        )
        pending_files = result.scalars().all()

        if not pending_files:
            return

        now = datetime.now(timezone.utc)
        timeout_threshold = now - timedelta(seconds=SCAN_TIMEOUT_SECONDS)
        s3 = get_s3_client()

        for file in pending_files:
            try:
                tagging_response = await asyncio.to_thread(
                    s3.get_object_tagging,
                    Bucket=settings.s3_quarantine_bucket,
                    Key=file.s3_key,
                )
                tags = {
                    tag["Key"]: tag["Value"]
                    for tag in tagging_response.get("TagSet", [])
                }
                scan_status = tags.get(GUARDDUTY_SCAN_STATUS_TAG)

                if scan_status == "NO_THREATS_FOUND":
                    await asyncio.to_thread(
                        s3.copy_object,
                        CopySource={
                            "Bucket": settings.s3_quarantine_bucket,
                            "Key": file.s3_key,
                        },
                        Bucket=settings.s3_wiki_bucket,
                        Key=file.s3_key,
                    )
                    await asyncio.to_thread(
                        s3.delete_object,
                        Bucket=settings.s3_quarantine_bucket,
                        Key=file.s3_key,
                    )
                    file.status = "clean"
                    file.transferred_at = now
                    logger.info("File clean: %s", file.s3_key)
                elif scan_status == GUARDDUTY_THREAT_STATUS_TAG:
                    try:
                        await asyncio.to_thread(
                            s3.delete_object,
                            Bucket=settings.s3_quarantine_bucket,
                            Key=file.s3_key,
                        )
                    except ClientError:
                        pass
                    file.status = "failed_scan"
                    logger.warning("Malware detected: %s", file.s3_key)
                elif file.scan_started_at < timeout_threshold:
                    file.status = "failed_timeout"
                    logger.warning("Scan timeout: %s", file.s3_key)

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code in ["404", "NotFound", "NoSuchKey"]:
                    file.status = "failed_upload"
                    logger.warning("File missing from S3: %s", file.s3_key)
                elif file.scan_started_at < timeout_threshold:
                    file.status = "failed_timeout"

        await db.commit()


async def scan_worker_loop():
    """Background loop that polls for pending scans every POLL_INTERVAL_SECONDS."""
    logger.info("Scan worker started (polling every %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await process_pending_scans()
        except Exception:
            logger.exception("Scan worker error")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
