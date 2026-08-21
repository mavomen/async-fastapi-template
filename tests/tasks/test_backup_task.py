"""Unit tests for database backup, restore, and cleanup Celery tasks."""

import gzip
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.backup import (
    _backup_key,
    _extract_key_timestamp,
    _make_sync_url,
    _parse_sync_url,
    backup_database,
    cleanup_old_backups,
    restore_backup,
)

# ---------------------------------------------------------------------------
# URL parsing helpers
# ---------------------------------------------------------------------------


class TestParseSyncUrl:
    def test_asyncpg_url(self) -> None:
        url = "postgresql+asyncpg://user:pass@host:5432/mydb"
        comps = _parse_sync_url(url)
        assert comps["host"] == "host"
        assert comps["port"] == "5432"
        assert comps["user"] == "user"
        assert comps["password"] == "pass"
        assert comps["dbname"] == "mydb"

    def test_plain_pg_url(self) -> None:
        url = "postgresql://admin:s3cret@db.internal:5433/fastapi_prod"
        comps = _parse_sync_url(url)
        assert comps["host"] == "db.internal"
        assert comps["port"] == "5433"
        assert comps["user"] == "admin"
        assert comps["password"] == "s3cret"
        assert comps["dbname"] == "fastapi_prod"

    def test_defaults_when_missing(self) -> None:
        url = "postgresql:///postgres"
        comps = _parse_sync_url(url)
        assert comps["host"] == "localhost"
        assert comps["port"] == "5432"
        assert comps["user"] == "postgres"
        assert comps["password"] == ""

    def test_encoded_password(self) -> None:
        url = "postgresql://user:p%40ss@host:5432/db"
        comps = _parse_sync_url(url)
        assert comps["password"] == "p@ss"


class TestMakeSyncUrl:
    def test_basic(self) -> None:
        comps = {
            "host": "localhost",
            "port": "5432",
            "user": "postgres",
            "password": "secret",
            "dbname": "testdb",
        }
        url = _make_sync_url(comps)
        assert url == "postgresql://postgres:secret@localhost:5432/testdb"


# ---------------------------------------------------------------------------
# Key generation / parsing
# ---------------------------------------------------------------------------


class TestBackupKey:
    def test_key_format(self) -> None:
        ts = datetime(2026, 1, 15, 2, 30, 45, tzinfo=UTC)
        key = _backup_key("fastapi_db", ts)
        assert key == "backups/fastapi_db/2026-01-15T02-30-45.dump.gz"

    def test_custom_prefix(self) -> None:
        ts = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
        with patch("app.tasks.backup.settings") as mock_s:
            mock_s.BACKUP_S3_PREFIX = "my-pg-dumps"
            key = _backup_key("app", ts)
            assert key == "my-pg-dumps/app/2026-06-01T00-00-00.dump.gz"


class TestExtractKeyTimestamp:
    def test_valid_key(self) -> None:
        ts = _extract_key_timestamp("backups/db/2026-03-10T14-00-00.dump.gz")
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 3
        assert ts.day == 10
        assert ts.hour == 14

    def test_invalid_key_returns_none(self) -> None:
        assert _extract_key_timestamp("not-a-backup-key.txt") is None

    def test_partial_timestamp_returns_none(self) -> None:
        assert _extract_key_timestamp("backups/db/2026-03-10.dump.gz") is None


# ---------------------------------------------------------------------------
# backup_database task
# ---------------------------------------------------------------------------


class TestBackupDatabase:
    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.subprocess.run")
    @patch("app.tasks.backup.settings")
    def test_successful_backup(
        self, mock_settings: MagicMock, mock_run: MagicMock, mock_s3: MagicMock
    ) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"

        dump_content = b"PGDMP custom format data"
        mock_run.return_value = MagicMock(returncode=0, stdout=dump_content, stderr=b"")

        result = backup_database()

        assert result["bytes_raw"] == len(dump_content)
        assert result["bytes_compressed"] > 0
        assert "key" in result
        assert result["key"].endswith(".dump.gz")

        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0][0] == "pg_dump"
        assert "-Fc" in args[0][0]

        mock_s3.return_value.put_object.assert_called_once()
        put_kwargs = mock_s3.return_value.put_object.call_args
        assert put_kwargs[1]["Bucket"] == "test-bucket"

    @patch("app.tasks.backup.subprocess.run")
    @patch("app.tasks.backup.settings")
    def test_pg_dump_failure_raises(self, mock_settings: MagicMock, mock_run: MagicMock) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )

        mock_run.return_value = MagicMock(returncode=1, stdout=b"", stderr=b"connection refused")

        with pytest.raises(RuntimeError, match="pg_dump failed"):
            backup_database()

    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.subprocess.run")
    @patch("app.tasks.backup.settings")
    def test_compression_reduces_size(
        self, mock_settings: MagicMock, mock_run: MagicMock, _mock_s3: MagicMock
    ) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"

        repetitive = b"REPEAT" * 10000
        mock_run.return_value = MagicMock(returncode=0, stdout=repetitive, stderr=b"")

        result = backup_database()

        assert result["bytes_raw"] == len(repetitive)
        assert result["bytes_compressed"] < result["bytes_raw"]


# ---------------------------------------------------------------------------
# cleanup_old_backups task
# ---------------------------------------------------------------------------


class TestCleanupOldBackups:
    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.settings")
    def test_deletes_old_backups(self, mock_settings: MagicMock, mock_s3: MagicMock) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"
        mock_settings.BACKUP_RETENTION_DAYS = 7

        now = datetime.now(UTC)
        old_key = (
            "backups/fastapi_db/"
            + (now - timedelta(days=10)).strftime("%Y-%m-%dT%H-%M-%S")
            + ".dump.gz"
        )
        new_key = (
            "backups/fastapi_db/"
            + (now - timedelta(days=2)).strftime("%Y-%m-%dT%H-%M-%S")
            + ".dump.gz"
        )

        client = mock_s3.return_value
        paginator_mock = MagicMock()
        paginator_mock.paginate.return_value = [
            {"Contents": [{"Key": old_key, "Size": 100}, {"Key": new_key, "Size": 200}]}
        ]
        client.get_paginator.return_value = paginator_mock

        result = cleanup_old_backups()

        assert result["deleted"] == 1
        assert old_key in result["keys"]
        assert new_key not in result["keys"]
        client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=old_key)

    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.settings")
    def test_no_backups_to_delete(self, mock_settings: MagicMock, mock_s3: MagicMock) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"
        mock_settings.BACKUP_RETENTION_DAYS = 30

        client = mock_s3.return_value
        paginator_mock = MagicMock()
        paginator_mock.paginate.return_value = [{"Contents": []}]
        client.get_paginator.return_value = paginator_mock

        result = cleanup_old_backups()

        assert result["deleted"] == 0
        assert result["keys"] == []
        client.delete_object.assert_not_called()


# ---------------------------------------------------------------------------
# restore_backup task
# ---------------------------------------------------------------------------


class TestRestoreBackup:
    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.subprocess.run")
    @patch("app.tasks.backup.settings")
    def test_restore_with_explicit_key(
        self, mock_settings: MagicMock, mock_run: MagicMock, mock_s3: MagicMock
    ) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"

        dump_data = b"PGDMP custom format data"
        compressed = gzip.compress(dump_data)

        client = mock_s3.return_value
        body_mock = MagicMock()
        body_mock.read.return_value = compressed
        client.get_object.return_value = {"Body": body_mock}

        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        result = restore_backup(key="backups/fastapi_db/2026-01-01T00-00-00.dump.gz")

        assert result["bytes_restored"] == len(dump_data)
        assert result["key"] == "backups/fastapi_db/2026-01-01T00-00-00.dump.gz"
        assert result["warnings"] is None

        mock_run.assert_called_once()
        args = mock_run.call_args
        assert args[0][0][0] == "pg_restore"
        assert "--clean" in args[0][0]

    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.subprocess.run")
    @patch("app.tasks.backup.settings")
    def test_restore_latest_when_no_key(
        self, mock_settings: MagicMock, mock_run: MagicMock, mock_s3: MagicMock
    ) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"

        now = datetime.now(UTC)
        key1 = (
            "backups/fastapi_db/"
            + (now - timedelta(days=2)).strftime("%Y-%m-%dT%H-%M-%S")
            + ".dump.gz"
        )
        key2 = (
            "backups/fastapi_db/"
            + (now - timedelta(days=1)).strftime("%Y-%m-%dT%H-%M-%S")
            + ".dump.gz"
        )

        client = mock_s3.return_value
        paginator_mock = MagicMock()
        paginator_mock.paginate.return_value = [
            {"Contents": [{"Key": key1, "Size": 100}, {"Key": key2, "Size": 200}]}
        ]
        client.get_paginator.return_value = paginator_mock

        compressed = gzip.compress(b"dump data")
        body_mock = MagicMock()
        body_mock.read.return_value = compressed
        client.get_object.return_value = {"Body": body_mock}
        mock_run.return_value = MagicMock(returncode=0, stdout=b"", stderr=b"")

        result = restore_backup()

        assert result["key"] == key2  # most recent

    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.settings")
    def test_restore_no_backups_raises(self, mock_settings: MagicMock, mock_s3: MagicMock) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"

        client = mock_s3.return_value
        paginator_mock = MagicMock()
        paginator_mock.paginate.return_value = [{"Contents": []}]
        client.get_paginator.return_value = paginator_mock

        with pytest.raises(RuntimeError, match="No backups found"):
            restore_backup()

    @patch("app.tasks.backup._make_s3_client")
    @patch("app.tasks.backup.subprocess.run")
    @patch("app.tasks.backup.settings")
    def test_restore_pg_restore_warning_accepted(
        self, mock_settings: MagicMock, mock_run: MagicMock, mock_s3: MagicMock
    ) -> None:
        mock_settings.DATABASE_URL = (
            "postgresql+asyncpg://postgres:postgres@localhost:5432/fastapi_db"
        )
        mock_settings.S3_BUCKET = "test-bucket"
        mock_settings.S3_ACCESS_KEY = "key"
        mock_settings.S3_SECRET_KEY = "secret"
        mock_settings.S3_ENDPOINT_URL = None
        mock_settings.S3_REGION = "us-east-1"
        mock_settings.BACKUP_S3_PREFIX = "backups/"

        compressed = gzip.compress(b"dump")
        body_mock = MagicMock()
        body_mock.read.return_value = compressed
        mock_s3.return_value.get_object.return_value = {"Body": body_mock}

        # rc=1 means warnings only
        mock_run.return_value = MagicMock(
            returncode=1, stdout=b"", stderr=b"WARNING: role does not exist"
        )

        result = restore_backup(key="backups/fastapi_db/2026-01-01T00-00-00.dump.gz")
        assert result["warnings"] is not None
        assert "role does not exist" in result["warnings"]


# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------


class TestTaskRegistration:
    def test_backup_task_registered(self) -> None:
        assert backup_database is not None
        assert hasattr(backup_database, "delay")

    def test_cleanup_task_registered(self) -> None:
        assert cleanup_old_backups is not None
        assert hasattr(cleanup_old_backups, "delay")

    def test_restore_task_registered(self) -> None:
        assert restore_backup is not None
        assert hasattr(restore_backup, "delay")
