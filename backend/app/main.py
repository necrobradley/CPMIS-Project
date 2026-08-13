"""
DigiCom PMIS - Main Application Entry Point
Digital Project Communication Management Information System
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import production_config_errors, settings
from app.core.rate_limit import (
    InMemoryRateLimiter,
    apply_security_headers,
    client_ip,
    default_rate_limit_rule,
    rule_for_request,
    sensitive_rate_limit_rules,
)
from app.api.v1.router import api_router
from app.db.database import bootstrap_feature_flags, bootstrap_project_memberships, create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
rate_limiter = InMemoryRateLimiter()

DEFAULT_RATE_LIMIT = default_rate_limit_rule(settings)
SENSITIVE_RATE_LIMITS = sensitive_rate_limit_rules(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    # Startup
    logger.info("Rencanix starting...")
    production_errors = production_config_errors(settings)
    if production_errors:
        message = "Production config tidak aman: " + "; ".join(production_errors)
        logger.error(message)
        raise RuntimeError(message)
    if settings.DATABASE_INIT_ON_STARTUP:
        create_tables()
        bootstrap_project_memberships()
        bootstrap_feature_flags()
        logger.info("Database tables created/verified")
    else:
        logger.info("Database startup initialization skipped; schema is managed separately")

    if settings.BACKGROUND_WORKERS_ENABLED:
        from app.services.scheduler import run_scheduler

        asyncio.create_task(run_scheduler())
        logger.info("Background scheduler started")

        if settings.TELEGRAM_BOT_ENABLED and settings.TELEGRAM_BOT_TOKEN:
            from app.services.telegram_service import run_bot_polling

            asyncio.create_task(run_bot_polling())
            logger.info("Telegram bot polling started")
        elif not settings.TELEGRAM_BOT_ENABLED:
            logger.warning("Telegram bot disabled by TELEGRAM_BOT_ENABLED=False")
        else:
            logger.warning("WARNING: TELEGRAM_BOT_TOKEN tidak diset, bot tidak dijalankan")
    else:
        logger.info(
            "Background workers disabled; gunakan Telegram webhook dan scheduler eksternal."
        )

    yield

    # Shutdown
    logger.info("Rencanix shutting down...")


# -----------------------------------------------------------------------------
# FASTAPI APP
# -----------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Rencanix - Intelligent Project Control

Platform pengendalian proyek yang mengintegrasikan AI, Telegram, audit trail, approval, dan otomasi alur kerja.

### Fitur Utama:
- **Authentication** - JWT-based login & role management
- **Projects** - Manajemen proyek multi-divisi
- **Tasks** - Issue/task board dengan audit trail
- **Approvals** - Approval center untuk dokumen, task, dan instruksi
- **Documents** - Document control dan Document QA dengan sumber
- **Daily Reports** - Laporan harian via web/Telegram + AI summary
- **AI Features** - Analisis dokumen, generate task, deteksi risiko
- **Research Export** - Dataset pilot untuk tesis dan validasi
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# MIDDLEWARE
# -----------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------

@app.middleware("http")
async def security_middleware(request, call_next):
    rule = None
    remaining = None
    if settings.RATE_LIMIT_ENABLED and request.url.path.startswith("/api/v1/"):
        rule = rule_for_request(request, SENSITIVE_RATE_LIMITS, DEFAULT_RATE_LIMIT)
        key = f"{rule.name}:{client_ip(request)}"
        allowed, remaining, retry_after = rate_limiter.check(
            key,
            limit=max(1, rule.limit),
            window_seconds=rule.window_seconds,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Terlalu banyak request. Coba lagi sebentar."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rule.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

    response = await call_next(request)
    apply_security_headers(response, debug=settings.DEBUG)
    if settings.RATE_LIMIT_ENABLED and rule:
        response.headers.setdefault("X-RateLimit-Limit", str(rule.limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
    return response


app.include_router(api_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}


# -----------------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLER
# -----------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "success": False}
    )
