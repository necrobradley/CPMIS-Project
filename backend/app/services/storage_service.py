"""
MinIO Storage Service - AI CPMIS
Upload, download, delete file + signed URL generation.
"""
import io
import logging
from typing import Optional
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
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
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Bucket '{self.bucket}' created.")
        except Exception as e:
            logger.warning(f"MinIO bucket check failed: {e}")

    def upload_file(self, file_data: bytes, object_name: str, content_type: str = "application/octet-stream") -> str:
        """Upload file ke MinIO, kembalikan path object."""
        try:
            self.client.put_object(
                self.bucket, object_name,
                io.BytesIO(file_data), length=len(file_data),
                content_type=content_type,
            )
            return object_name
        except S3Error as e:
            logger.error(f"Upload error: {e}")
            raise

    def get_signed_url(self, object_name: str, expires_hours: int = 1) -> str:
        """Generate signed URL untuk akses file private (expires sesuai setting)."""
        try:
            url = self.client.presigned_get_object(
                self.bucket, object_name,
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
        except S3Error as e:
            logger.error(f"Signed URL error: {e}")
            raise

    def get_file_bytes(self, object_name: str) -> bytes:
        """Download object private dari MinIO/S3 sebagai bytes."""
        response = None
        try:
            response = self.client.get_object(self.bucket, object_name)
            return response.read()
        except S3Error as e:
            logger.error(f"Download error: {e}")
            raise
        finally:
            if response:
                response.close()
                response.release_conn()

    def delete_file(self, object_name: str) -> bool:
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error as e:
            logger.error(f"Delete error: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error:
            return False


storage_service = StorageService()
