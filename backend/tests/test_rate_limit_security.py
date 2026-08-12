from types import SimpleNamespace

from starlette.responses import Response

from app.core.rate_limit import (
    InMemoryRateLimiter,
    RateLimitRule,
    apply_security_headers,
    default_rate_limit_rule,
    rule_for_request,
    sensitive_rate_limit_rules,
)


class DummyUrl:
    def __init__(self, path: str):
        self.path = path


class DummyRequest:
    def __init__(self, path: str, method: str = "POST"):
        self.url = DummyUrl(path)
        self.method = method


def test_in_memory_rate_limiter_blocks_after_limit():
    limiter = InMemoryRateLimiter()

    assert limiter.check("auth:127.0.0.1", limit=2, window_seconds=60, now=100.0) == (True, 1, 0)
    assert limiter.check("auth:127.0.0.1", limit=2, window_seconds=60, now=101.0) == (True, 0, 0)
    allowed, remaining, retry_after = limiter.check("auth:127.0.0.1", limit=2, window_seconds=60, now=102.0)

    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_in_memory_rate_limiter_resets_after_window():
    limiter = InMemoryRateLimiter()

    limiter.check("upload:10.0.0.1", limit=1, window_seconds=60, now=100.0)
    allowed, remaining, retry_after = limiter.check("upload:10.0.0.1", limit=1, window_seconds=60, now=161.0)

    assert allowed is True
    assert remaining == 0
    assert retry_after == 0


def test_rule_for_request_prioritizes_sensitive_routes():
    default = RateLimitRule("default", ("/api/v1/",), ("GET", "POST"), 120)
    rules = [
        RateLimitRule("auth", ("/api/v1/auth/login",), ("POST",), 8),
        RateLimitRule("ai", ("/api/v1/ai/",), ("POST",), 30),
    ]

    assert rule_for_request(DummyRequest("/api/v1/auth/login"), rules, default).name == "auth"
    assert rule_for_request(DummyRequest("/api/v1/ai/chat"), rules, default).name == "ai"
    assert rule_for_request(DummyRequest("/api/v1/projects", "GET"), rules, default).name == "default"


def test_rate_limit_rule_builders_use_settings():
    settings = SimpleNamespace(
        RATE_LIMIT_DEFAULT_PER_MINUTE=100,
        RATE_LIMIT_AUTH_PER_MINUTE=7,
        RATE_LIMIT_UPLOAD_PER_MINUTE=20,
        RATE_LIMIT_AI_PER_MINUTE=12,
        RATE_LIMIT_WEBHOOK_PER_MINUTE=30,
    )

    default = default_rate_limit_rule(settings)
    sensitive = {rule.name: rule for rule in sensitive_rate_limit_rules(settings)}

    assert default.limit == 100
    assert sensitive["auth"].limit == 7
    assert sensitive["upload"].limit == 20
    assert sensitive["ai"].limit == 12
    assert sensitive["webhook"].limit == 30


def test_apply_security_headers_adds_production_headers():
    response = Response()

    apply_security_headers(response, debug=False)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_apply_security_headers_skips_hsts_in_debug():
    response = Response()

    apply_security_headers(response, debug=True)

    assert "Strict-Transport-Security" not in response.headers
