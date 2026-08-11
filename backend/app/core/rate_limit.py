import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Protocol

from fastapi import Request
from starlette.responses import Response


class RateLimitSettings(Protocol):
    RATE_LIMIT_DEFAULT_PER_MINUTE: int
    RATE_LIMIT_AUTH_PER_MINUTE: int
    RATE_LIMIT_UPLOAD_PER_MINUTE: int
    RATE_LIMIT_AI_PER_MINUTE: int
    RATE_LIMIT_WEBHOOK_PER_MINUTE: int


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    path_prefixes: tuple[str, ...]
    methods: tuple[str, ...]
    limit: int
    window_seconds: int = 60


class InMemoryRateLimiter:
    """Small per-process limiter for pilot deployments.

    Production with multiple backend replicas should replace this with Redis-backed limits.
    """

    def __init__(self):
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int, now: float | None = None) -> tuple[bool, int, int]:
        now = now if now is not None else time.monotonic()
        hits = self._hits[key]
        cutoff = now - window_seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            return False, 0, retry_after
        hits.append(now)
        return True, max(0, limit - len(hits)), 0

    def reset(self) -> None:
        self._hits.clear()


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def rule_for_request(request: Request, rules: list[RateLimitRule], default_rule: RateLimitRule) -> RateLimitRule:
    path = request.url.path
    method = request.method.upper()
    for rule in rules:
        if method in rule.methods and any(path.startswith(prefix) for prefix in rule.path_prefixes):
            return rule
    return default_rule


def default_rate_limit_rule(settings: RateLimitSettings) -> RateLimitRule:
    return RateLimitRule(
        name="default",
        path_prefixes=("/api/v1/",),
        methods=("GET", "POST", "PUT", "PATCH", "DELETE"),
        limit=settings.RATE_LIMIT_DEFAULT_PER_MINUTE,
    )


def sensitive_rate_limit_rules(settings: RateLimitSettings) -> list[RateLimitRule]:
    return [
        RateLimitRule(
            name="auth",
            path_prefixes=("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"),
            methods=("POST",),
            limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        ),
        RateLimitRule(
            name="upload",
            path_prefixes=("/api/v1/documents/upload", "/api/v1/reports/"),
            methods=("POST",),
            limit=settings.RATE_LIMIT_UPLOAD_PER_MINUTE,
        ),
        RateLimitRule(
            name="ai",
            path_prefixes=("/api/v1/ai/", "/api/v1/documents/qa"),
            methods=("POST",),
            limit=settings.RATE_LIMIT_AI_PER_MINUTE,
        ),
        RateLimitRule(
            name="webhook",
            path_prefixes=("/api/v1/n8n/",),
            methods=("POST",),
            limit=settings.RATE_LIMIT_WEBHOOK_PER_MINUTE,
        ),
    ]


def apply_security_headers(response: Response, debug: bool) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cache-Control", "no-store")
    if not debug:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
