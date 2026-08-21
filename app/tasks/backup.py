"""Celery tasks for automated PostgreSQL backup, restore, and retention cleanup."""

import gzip
import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import unquote, urlparse

import boto3
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.core.config import settings
from app.tasks.base import BaseTask

logger = get_task_logger(__name__)

_DUMP_TIMEOUT = 300  # seconds
_RESTORE_TIMEOUT = 600  # seconds
_DRAIN_TIMEOUT = 30


def _parse_sync_url(database_url: str) -> dict[str, str]:
    """Extract connection components from a PostgreSQL URL (any driver prefix)."""
    url = urlparse(database_url)
    return {
        "host": url.hostname or "localhost",
        "port": str(url.port or 5432),
        "user": unquote(url.username or "postgres"),
        "password": unquote(url.password or ""),
        "dbname": unquote(url.path.lstrip("/") or "postgres"),
    }


def _make_sync_url(components: dict[str, str]) -> str:
    """Build a plain ``postgresql://`` URL suitable for pg_dump / pg_restore."""
    return (
        f"postgresql://{components['user']}:{components['password']}"
        f"@{components['host']}:{components['port']}/{components['dbname']}"
    )


def _make_s3_client() -> Any:
    """Create a synchronous boto3 S3 client."""
    kwargs: dict[str, Any] = {
        "service_name": "s3",
        "region_name": settings.S3_REGION,
    }
    if settings.S3_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.S3_ACCESS_KEY
        kwargs["aws_secret_access_key"] = settings.S3_SECRET_KEY
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client(**kwargs)


def _backup_key(db_name: str, ts: datetime) -> str:
    """Generate the S3 key for a backup file."""
    prefix = settings.BACKUP_S3_PREFIX.rstrip("/")
    stamp = ts.strftime("%Y-%m-%dT%H-%M-%S")
    return f"{prefix}/{db_name}/{stamp}.dump.gz"


def _extract_key_timestamp(key: str) -> datetime | None:
    """Parse the ``YYYY-MM-DDTHH-MM-SS`` timestamp from a backup key."""
    match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})\.dump\.gz$", key)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%dT%H-%M-%S").replace(tzinfo=UTC)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Backup task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, base=BaseTask, max_retries=1)  # type: ignore[untyped-decorator]
def backup_database(self: Any) -> dict[str, Any]:
    """Run ``pg_dump`` and upload the compressed dump to S3."""
    comps = _parse_sync_url(settings.DATABASE_URL)
    db_name = comps["dbname"]
    sync_url = _make_sync_url(comps)
    now = datetime.now(UTC)
    key = _backup_key(db_name, now)

    logger.info("Starting backup for database '%s' → s3://%s/%s", db_name, settings.S3_BUCKET, key)
    t0 = time.monotonic()

    # pg_dump with custom format (Fc) for efficient restore
    dump_cmd = [
        "pg_dump",
        "-Fc",
        "--no-owner",
        "--no-privileges",
        sync_url,
    ]

    result = subprocess.run(
        dump_cmd,
        capture_output=True,
        check=False,
        timeout=_DUMP_TIMEOUT,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        logger.error("pg_dump failed (rc=%d): %s", result.returncode, stderr)
        raise RuntimeError(f"pg_dump failed with code {result.returncode}: {stderr}")

    raw_dump = result.stdout
    compressed = gzip.compress(raw_dump, compresslevel=6)

    s3 = _make_s3_client()
    s3.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=compressed)

    elapsed = time.monotonic() - t0
    logger.info(
        "Backup complete: %s bytes raw → %s bytes compressed in %.1fs",
        len(raw_dump),
        len(compressed),
        elapsed,
    )
    return {
        "key": key,
        "bytes_raw": len(raw_dump),
        "bytes_compressed": len(compressed),
        "elapsed_seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Cleanup task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, base=BaseTask, max_retries=1)  # type: ignore[untyped-decorator]
def cleanup_old_backups(self: Any) -> dict[str, Any]:
    """Delete backup objects in S3 older than ``BACKUP_RETENTION_DAYS``."""
    comps = _parse_sync_url(settings.DATABASE_URL)
    db_name = comps["dbname"]
    prefix = f"{settings.BACKUP_S3_PREFIX.rstrip('/')}/{db_name}/"
    cutoff = datetime.now(UTC) - timedelta(days=settings.BACKUP_RETENTION_DAYS)

    s3 = _make_s3_client()
    deleted: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            ts = _extract_key_timestamp(key)
            if ts is not None and ts < cutoff:
                s3.delete_object(Bucket=settings.S3_BUCKET, Key=key)
                deleted.append(key)
                logger.info("Deleted expired backup: %s", key)

    logger.info("Cleanup finished: %d backup(s) deleted", len(deleted))
    return {"deleted": len(deleted), "keys": deleted}


# ---------------------------------------------------------------------------
# Restore task (manual trigger)
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, base=BaseTask, max_retries=0)  # type: ignore[untyped-decorator]
def restore_backup(self: Any, key: str | None = None) -> dict[str, Any]:
    """Download a backup from S3 and restore it via ``pg_restore``.

    When *key* is ``None`` the most recent backup for the database is used.
    """
    comps = _parse_sync_url(settings.DATABASE_URL)
    db_name = comps["dbname"]
    sync_url = _make_sync_url(comps)
    s3 = _make_s3_client()

    if key is None:
        prefix = f"{settings.BACKUP_S3_PREFIX.rstrip('/')}/{db_name}/"
        paginator = s3.get_paginator("list_objects_v2")
        candidates: list[tuple[str, datetime]] = []
        for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                ts = _extract_key_timestamp(obj["Key"])
                if ts is not None:
                    candidates.append((obj["Key"], ts))
        if not candidates:
            raise RuntimeError(f"No backups found under s3://{settings.S3_BUCKET}/{prefix}")
        candidates.sort(key=lambda c: c[1], reverse=True)
        key = candidates[0][0]

    logger.info("Restoring from s3://%s/%s → database '%s'", settings.S3_BUCKET, key, db_name)
    t0 = time.monotonic()

    s3_obj = s3.get_object(Bucket=settings.S3_BUCKET, Key=key)
    compressed = s3_obj["Body"].read()
    dump_data = gzip.decompress(compressed)

    result = subprocess.run(
        ["pg_restore", "--clean", "--no-owner", "--no-privileges", "-d", db_name, sync_url],
        input=dump_data,
        capture_output=True,
        check=False,
        timeout=_RESTORE_TIMEOUT,
    )

    elapsed = time.monotonic() - t0

    # pg_restore exits 1 for warnings (e.g. "role does not exist") which is acceptable
    if result.returncode > 1:
        stderr = result.stderr.decode(errors="replace").strip()
        logger.error("pg_restore failed (rc=%d): %s", result.returncode, stderr)
        raise RuntimeError(f"pg_restore failed with code {result.returncode}: {stderr}")

    logger.info("Restore complete from '%s' in %.1fs", key, elapsed)
    return {
        "key": key,
        "bytes_restored": len(dump_data),
        "elapsed_seconds": round(elapsed, 1),
        "warnings": result.stderr.decode(errors="replace").strip()
        if result.returncode == 1
        else None,
    }
