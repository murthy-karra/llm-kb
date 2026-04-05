from pathlib import Path

import boto3

from .config import settings


def get_aws_session() -> boto3.Session:
    """Return a boto3 session using the configured AWS profile."""
    return boto3.Session(
        profile_name=settings.aws_profile,
        region_name=settings.aws_region,
    )


def get_s3_client():
    """Return an S3 client using the configured AWS profile."""
    from botocore.config import Config
    return get_aws_session().client(
        "s3",
        region_name=settings.aws_region,
        endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
        config=Config(signature_version="s3v4"),
    )


def upload_to_quarantine(file_path: Path, s3_key: str) -> str:
    """Upload a file to the quarantine bucket for GuardDuty scanning.

    Returns the S3 URI of the uploaded object.
    """
    s3 = get_s3_client()
    s3.upload_file(str(file_path), settings.s3_quarantine_bucket, s3_key)
    return f"s3://{settings.s3_quarantine_bucket}/{s3_key}"


def move_to_wiki_bucket(s3_key: str) -> str:
    """Move a scanned file from quarantine to the wiki bucket.

    Call this after GuardDuty marks the file as clean.
    Returns the S3 URI in the wiki bucket.
    """
    s3 = get_s3_client()
    copy_source = {"Bucket": settings.s3_quarantine_bucket, "Key": s3_key}
    s3.copy_object(
        CopySource=copy_source,
        Bucket=settings.s3_wiki_bucket,
        Key=s3_key,
    )
    s3.delete_object(Bucket=settings.s3_quarantine_bucket, Key=s3_key)
    return f"s3://{settings.s3_wiki_bucket}/{s3_key}"


def download_from_wiki_bucket(s3_key: str, dest_path: Path) -> Path:
    """Download a file from the wiki bucket to a local path."""
    s3 = get_s3_client()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(settings.s3_wiki_bucket, str(s3_key), str(dest_path))
    return dest_path


def read_s3_text(s3_key: str, bucket: str | None = None) -> str:
    """Read an S3 object and return its content as text."""
    s3 = get_s3_client()
    target_bucket = bucket or settings.s3_wiki_bucket
    response = s3.get_object(Bucket=target_bucket, Key=s3_key)
    return response["Body"].read().decode("utf-8", errors="replace")


def generate_presigned_upload_url(
    s3_key: str,
    content_type: str,
    max_size_bytes: int = 10 * 1024 * 1024,
    expires_in: int = 900,
) -> dict:
    """Generate a presigned POST for uploading a file to S3 quarantine bucket.

    Uses presigned POST (not PUT) to enforce content-length-range via policy
    conditions, preventing clients from uploading files larger than max_size_bytes.

    Returns dict with 'url' and 'fields' for the POST form data.
    """
    s3 = get_s3_client()
    return s3.generate_presigned_post(
        Bucket=settings.s3_quarantine_bucket,
        Key=s3_key,
        Fields={"Content-Type": content_type},
        Conditions=[
            ["content-length-range", 1, max_size_bytes],
            ["eq", "$Content-Type", content_type],
        ],
        ExpiresIn=expires_in,
    )
