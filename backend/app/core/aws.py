from pathlib import Path

import boto3

from .config import settings


def get_aws_session() -> boto3.Session:
    """Return a boto3 session using the configured AWS profile."""
    return boto3.Session(profile_name=settings.aws_profile)


def get_s3_client():
    """Return an S3 client using the configured AWS profile."""
    return get_aws_session().client("s3")


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
