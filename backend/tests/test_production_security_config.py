from types import SimpleNamespace

from app.core.config import production_config_errors


def test_production_config_rejects_default_secrets_and_local_origins():
    config = SimpleNamespace(
        DEBUG=False,
        SECRET_KEY="change-this-in-production",
        ALLOWED_ORIGINS=["http://localhost:3000"],
        MINIO_ACCESS_KEY="minioadmin",
        MINIO_SECRET_KEY="minioadmin",
        N8N_WEBHOOK_SECRET="cpmis-n8n-secret-2024",
        DATABASE_URL="postgresql://postgres:password@localhost:5432/ai_cpmis_db",
        RATE_LIMIT_ENABLED=False,
    )

    errors = production_config_errors(config)

    assert any("SECRET_KEY" in item for item in errors)
    assert any("ALLOWED_ORIGINS" in item for item in errors)
    assert any("MinIO" in item for item in errors)
    assert any("N8N_WEBHOOK_SECRET" in item for item in errors)
    assert any("DATABASE_URL" in item for item in errors)
    assert any("RATE_LIMIT_ENABLED" in item for item in errors)


def test_production_config_accepts_strong_public_settings():
    config = SimpleNamespace(
        DEBUG=False,
        SECRET_KEY="x" * 64,
        ALLOWED_ORIGINS=["https://pmis.example.com"],
        MINIO_ACCESS_KEY="digicom_minio",
        MINIO_SECRET_KEY="strong-minio-secret-value",
        N8N_WEBHOOK_SECRET="strong-n8n-secret-value",
        DATABASE_URL="postgresql://digicom:strong-password@postgres:5432/digicom_pmis",
        RATE_LIMIT_ENABLED=True,
    )

    assert production_config_errors(config) == []
