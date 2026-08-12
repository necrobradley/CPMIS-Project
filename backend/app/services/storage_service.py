"""Private object storage used by documents, evidence, and Telegram uploads.

Production on Vercel uses a private Vercel Blob store. MinIO remains available
for local development and existing Docker installations.
"""
from __future__ import annotations

import io
import logging
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinioStorageService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        public_endpoint = settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT
        public_secure = settings.MINIO_PUBLIC_SECURE if settings.MINIO_PUBLIC_ENDPOINT else settings.MINIO_SECURE
        self.public_client = Minio(
            public_endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=public_secure,
        )
        self.bucket = settings.MINIO_BUCKET_NAME
        self._bucket_ready = False

    def _ensure_bucket(self):
        if self._bucket_ready:
            return
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("Bucket '%s' created.", self.bucket)
            self._bucket_ready = True
        except Exception as exc:
            logger.warning("MinIO bucket check failed: %s", exc)

    def upload_file(self, file_data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
        self._ensure_bucket()
        self.client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
        )
        return object_name

    def get_signed_url(self, object_name: str, expires_hours: int = 1) -> str:
        url = self.client.presigned_get_object(
            self.bucket,
            object_name,
            expires=timedelta(hours=expires_hours),
        )
        if settings.MINIO_PUBLIC_ENDPOINT:
            parts = urlsplit(url)
            public_scheme = "https" if settings.MINIO_PUBLIC_SECURE else "http"
            url = urlunsplit((
                public_scheme,
                settings.MINIO_PUBLIC_ENDPOINT,
                parts.path,
                parts.query,
                parts.fragment,
            ))
        return url

    def get_file_bytes(self, object_name: str) -> bytes:
        response = None
        try:
            response = self.client.get_object(self.bucket, object_name)
            return response.read()
        finally:
            if response:
                response.close()
                response.release_conn()

    def delete_file(self, object_name: str) -> bool:
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error as exc:
            logger.error("Delete error: %s", exc)
            return False

    def file_exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False


class VercelBlobStorageService:
    """Synchronous adapter around the official Vercel Blob Python SDK."""

    def __init__(self):
        from vercel.blob import BlobClient

        self.client = BlobClient(token=settings.BLOB_READ_WRITE_TOKEN or None)

    def upload_file(self, file_data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
        result = self.client.put(
            object_name,
            file_data,
            access="private",
            content_type=content_type,
            overwrite=False,
        )
        return result.pathname

    def get_file_bytes(self, object_name: str) -> bytes:
        result = self.client.get(object_name, access="private", use_cache=False)
        if result is None or result.status_code != 200:
            raise FileNotFoundError(object_name)
        return result.content

    def get_signed_url(self, object_name: str, expires_hours: int = 1) -> str:
        # Private Blob reads must be proxied by an authenticated API route.
        # Keep this method explicit so callers cannot accidentally expose a
        # private store URL as if it were a presigned MinIO URL.
        raise RuntimeError("Vercel Blob private files must be downloaded through the authenticated API")

    def delete_file(self, object_name: str) -> bool:
        self.client.delete(object_name)
        return True

    def file_exists(self, object_name: str) -> bool:
        try:
            self.client.head(object_name)
            return True
        except Exception:
            return False


def build_storage_service():
    if settings.STORAGE_TYPE.strip().lower() == "vercel_blob":
        return VercelBlobStorageService()
    return MinioStorageService()


# Backward-compatible name for code that imports StorageService directly.
StorageService = MinioStorageService
storage_service = build_storage_service()
