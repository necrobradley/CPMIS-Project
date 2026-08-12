from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "DigiCom PMIS"
    APP_VERSION: str = "2.6.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/ai_cpmis_db"
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ai_cpmis_logs"

    # JWT
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_ENABLED: bool = True
    TELEGRAM_AI_PARSE_ENABLED: bool = False

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # AI Routing
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    AI_MODEL: str = ""
    AI_DEFAULT_PROVIDER: str = "openai"
    AI_DEFAULT_MODEL: str = ""
    AI_ANALYSIS_PROVIDER: str = ""
    AI_ANALYSIS_MODEL: str = ""
    AI_ANALYSIS_MAX_TOKENS: int = 4096
    AI_VISION_PROVIDER: str = ""
    AI_VISION_MODEL: str = ""
    AI_VISION_MAX_TOKENS: int = 2048
    AI_FALLBACK_PROVIDER: str = "openai"
    AI_FALLBACK_MODEL: str = ""
    AI_DEFAULT_MAX_TOKENS: int = 2048
    AI_MAX_TOKENS: int = 2048
    AI_TEMPERATURE: float = 0.2
    AI_TIMEOUT_SECONDS: int = 90
    AI_SAFETY_ENABLED: bool = True
    AI_SAFETY_MODE: str = "local"
    AI_GATEWAY_ENABLED: bool = True
    AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY: str = "mask"  # mask|block|allow
    AI_GATEWAY_MASK_FINANCIAL: bool = True
    AI_GATEWAY_MAX_PROMPT_CHARS: int = 24000
    AI_LOCAL_ENABLED: bool = False
    AI_LOCAL_PROVIDER: str = "ollama"
    OLLAMA_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "qwen3:8b"
    VLLM_API_KEY: str = ""
    VLLM_BASE_URL: str = "http://localhost:8008/v1"
    VLLM_MODEL: str = "Qwen/Qwen3-14B"
    LMSTUDIO_API_KEY: str = ""
    LMSTUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LMSTUDIO_MODEL: str = "qwen3-8b"
    # Generic serverless model endpoints (for example mlapi.run). One API key
    # can serve multiple URL-per-model entries through MLAPI_MODELS_JSON.
    MLAPI_API_KEY: str = ""
    MLAPI_BASE_URL: str = ""
    MLAPI_MODEL: str = "nemotron-3-ultra"
    MLAPI_MODELS_JSON: str = ""
    MLAPI_PAYLOAD_STYLE: str = "messages"  # messages|prompt|input
    MLAPI_INCLUDE_MODEL: bool = False
    MLAPI_EXTRA_PAYLOAD_JSON: str = ""
    RAG_ENABLED: bool = True
    RAG_CHUNK_SIZE: int = 1200
    RAG_CHUNK_OVERLAP: int = 180
    RAG_TOP_K: int = 6
    RAG_EMBEDDING_DIMENSIONS: int = 384

    # OpenAI-compatible provider keys
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    GLM_API_KEY: str = ""
    GLM_BASE_URL: str = "https://api.z.ai/api/paas/v4"
    GLM_MODEL: str = "glm-5.2"
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    GEMINI_MODEL: str = "gemini-3.1-flash-lite"
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3-nano-30b-a3b"
    DEEPINFRA_API_KEY: str = ""
    DEEPINFRA_BASE_URL: str = "https://api.deepinfra.com/v1/openai"
    DEEPINFRA_MODEL: str = "deepseek-ai/DeepSeek-V4-Flash"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "deepseek/deepseek-v4-flash"
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Storage
    STORAGE_TYPE: str = "minio"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "digicom-pmis-files"
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_ENDPOINT: str = ""
    MINIO_PUBLIC_SECURE: bool = True

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Security hardening
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
    RATE_LIMIT_AUTH_PER_MINUTE: int = 8
    RATE_LIMIT_UPLOAD_PER_MINUTE: int = 20
    RATE_LIMIT_AI_PER_MINUTE: int = 30
    RATE_LIMIT_WEBHOOK_PER_MINUTE: int = 60

    # N8N
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook"
    N8N_WEBHOOK_SECRET: str = "cpmis-n8n-secret-2024"

    # Runtime workers. Disable on serverless deployments; use webhooks/cron.
    BACKGROUND_WORKERS_ENABLED: bool = True
    TELEGRAM_WEBHOOK_SECRET: str = ""
    BOOTSTRAP_SECRET: str = ""
    BOOTSTRAP_MAX_UPLOAD_MB: int = 20
    DEMO_ADMIN_EMAIL: str = "admin.mnbc@demo.local"
    DEMO_ADMIN_PASSWORD: str = ""
    DEMO_TELEGRAM_ID: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


def production_config_errors(config=settings) -> List[str]:
    """Return blocking configuration errors for public production mode."""
    if config.DEBUG:
        return []

    errors: List[str] = []
    weak_secret_values = {
        "change-this-in-production",
        "ai-cpmis-local-dev-change-this",
        "CHANGE_ME_USE_A_LONG_RANDOM_64_CHAR_SECRET",
    }
    if not config.SECRET_KEY or config.SECRET_KEY in weak_secret_values or len(config.SECRET_KEY) < 48:
        errors.append("SECRET_KEY production harus random, unik, dan minimal 48 karakter")

    origins = config.ALLOWED_ORIGINS or []
    if not origins:
        errors.append("ALLOWED_ORIGINS production wajib diisi domain HTTPS resmi")
    for origin in origins:
        lowered = origin.lower()
        if origin == "*" or lowered.startswith("http://") or "localhost" in lowered or "127.0.0.1" in lowered:
            errors.append("ALLOWED_ORIGINS production tidak boleh wildcard, localhost, 127.0.0.1, atau HTTP")
            break

    if config.MINIO_ACCESS_KEY == "minioadmin" or config.MINIO_SECRET_KEY == "minioadmin":
        errors.append("Credential MinIO production tidak boleh memakai default minioadmin")
    if config.N8N_WEBHOOK_SECRET in {"cpmis-n8n-secret-2024", "CHANGE_ME_STRONG_N8N_SECRET", ""}:
        errors.append("N8N_WEBHOOK_SECRET production harus diganti dengan secret kuat")
    if "postgres:password@" in config.DATABASE_URL or "localhost" in config.DATABASE_URL:
        errors.append("DATABASE_URL production tidak boleh memakai password default atau localhost")
    if not getattr(config, "RATE_LIMIT_ENABLED", True):
        errors.append("RATE_LIMIT_ENABLED production tidak boleh dimatikan")

    return errors
