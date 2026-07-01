"""Tests for file storage backends and CDN URL generation."""

from unittest.mock import MagicMock, patch

from app.storage.base import StorageBackend
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


class TestStorageBackend:
    def test_get_url_defaults_to_none(self):
        class _MinimalStorage(StorageBackend):
            async def upload(self, _file, filename):
                return filename

            async def download(self, _path):
                return b""

            async def delete(self, _path):
                pass

        backend = _MinimalStorage()
        assert backend.get_url("some/key.jpg") is None


class TestS3Storage:
    _S3_CDN_SETTINGS = MagicMock(
        CDN_DOMAIN="cdn.example.com",
        S3_BUCKET="my-bucket",
        S3_REGION="us-east-1",
        S3_ENDPOINT_URL=None,
        S3_ACCESS_KEY="",
        S3_SECRET_KEY="",
    )
    _S3_NO_CDN_SETTINGS = MagicMock(
        CDN_DOMAIN="",
        S3_BUCKET="my-bucket",
        S3_REGION="us-east-1",
        S3_ENDPOINT_URL=None,
        S3_ACCESS_KEY="",
        S3_SECRET_KEY="",
    )

    def test_get_url_with_cdn(self):
        with patch("app.storage.s3.settings", self._S3_CDN_SETTINGS):
            backend = S3Storage()
            url = backend.get_url("uploads/image.jpg")
        assert url == "https://cdn.example.com/uploads/image.jpg"

    def test_get_url_with_cdn_special_chars(self):
        with patch("app.storage.s3.settings", self._S3_CDN_SETTINGS):
            backend = S3Storage()
            url = backend.get_url("uploads/file name+.jpg")
        assert url == "https://cdn.example.com/uploads/file%20name%2B.jpg"

    def test_get_url_without_cdn(self):
        with patch("app.storage.s3.settings", self._S3_NO_CDN_SETTINGS):
            backend = S3Storage()
            url = backend.get_url("uploads/image.jpg")
        assert url is None


class TestLocalStorage:
    _LOCAL_SETTINGS = MagicMock(
        CDN_DOMAIN="cdn.example.com",
        LOCAL_STORAGE_PATH="./uploads",
    )

    def test_get_url_always_none(self):
        with patch("app.storage.local.settings", self._LOCAL_SETTINGS):
            backend = LocalStorage()
            url = backend.get_url("uploads/image.jpg")
        assert url is None
