from types import SimpleNamespace

import pytest

from app.services.storage_service import VercelBlobStorageService


def test_private_blob_download_returns_sdk_content():
    service = VercelBlobStorageService.__new__(VercelBlobStorageService)
    service.client = SimpleNamespace(
        get=lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            content=b"private-file-content",
        )
    )

    assert service.get_file_bytes("documents/demo.txt") == b"private-file-content"


def test_private_blob_download_rejects_missing_object():
    service = VercelBlobStorageService.__new__(VercelBlobStorageService)
    service.client = SimpleNamespace(
        get=lambda *args, **kwargs: SimpleNamespace(status_code=404, content=b"")
    )

    with pytest.raises(FileNotFoundError):
        service.get_file_bytes("documents/missing.txt")
