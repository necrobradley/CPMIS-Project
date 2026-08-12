"""AI provider routing utilities.

This module keeps provider aliases, route resolution, fallback ordering, and
local-LLM status out of AIService so feature prompts remain easier to review.
"""
from __future__ import annotations

import json
from typing import Optional

from app.core.config import settings


PROVIDER_ALIASES = {
    "zai": "glm",
    "z.ai": "glm",
    "google": "gemini",
    "vertex": "gemini",
    "nemotron": "nvidia",
    "local": "ollama",
    "qwen-local": "ollama",
    "lm-studio": "lmstudio",
    "mlapi.run": "mlapi",
    "serverless": "mlapi",
}

LOCAL_PROVIDERS = {"ollama", "vllm", "lmstudio"}

PROVIDERS = {
    "openai": {
        "key": "OPENAI_API_KEY",
        "base_url": "OPENAI_BASE_URL",
        "model": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
    },
    "deepseek": {
        "key": "DEEPSEEK_API_KEY",
        "base_url": "DEEPSEEK_BASE_URL",
        "model": "DEEPSEEK_MODEL",
        "default_model": "deepseek-v4-flash",
    },
    "glm": {
        "key": "GLM_API_KEY",
        "base_url": "GLM_BASE_URL",
        "model": "GLM_MODEL",
        "default_model": "glm-5.2",
    },
    "gemini": {
        "key": "GEMINI_API_KEY",
        "base_url": "GEMINI_BASE_URL",
        "model": "GEMINI_MODEL",
        "default_model": "gemini-3.1-flash-lite",
    },
    "qwen": {
        "key": "QWEN_API_KEY",
        "base_url": "QWEN_BASE_URL",
        "model": "QWEN_MODEL",
        "default_model": "qwen-plus",
    },
    "nvidia": {
        "key": "NVIDIA_API_KEY",
        "base_url": "NVIDIA_BASE_URL",
        "model": "NVIDIA_MODEL",
        "default_model": "nvidia/nemotron-3-nano-30b-a3b",
    },
    "deepinfra": {
        "key": "DEEPINFRA_API_KEY",
        "base_url": "DEEPINFRA_BASE_URL",
        "model": "DEEPINFRA_MODEL",
        "default_model": "deepseek-ai/DeepSeek-V4-Flash",
    },
    "openrouter": {
        "key": "OPENROUTER_API_KEY",
        "base_url": "OPENROUTER_BASE_URL",
        "model": "OPENROUTER_MODEL",
        "default_model": "deepseek/deepseek-v4-flash",
    },
    "groq": {
        "key": "GROQ_API_KEY",
        "base_url": "GROQ_BASE_URL",
        "model": "GROQ_MODEL",
        "default_model": "openai/gpt-oss-20b",
    },
    "ollama": {
        "key": "OLLAMA_API_KEY",
        "base_url": "OLLAMA_BASE_URL",
        "model": "OLLAMA_MODEL",
        "default_model": "qwen3:8b",
    },
    "vllm": {
        "key": "VLLM_API_KEY",
        "base_url": "VLLM_BASE_URL",
        "model": "VLLM_MODEL",
        "default_model": "Qwen/Qwen3-14B",
    },
    "lmstudio": {
        "key": "LMSTUDIO_API_KEY",
        "base_url": "LMSTUDIO_BASE_URL",
        "model": "LMSTUDIO_MODEL",
        "default_model": "qwen3-8b",
    },
    "mlapi": {
        "key": "MLAPI_API_KEY",
        "base_url": "MLAPI_BASE_URL",
        "model": "MLAPI_MODEL",
        "default_model": "nemotron-3-ultra",
        "driver": "mlapi",
    },
}


def normalize_provider(provider: Optional[str]) -> str:
    value = (provider or "").strip().lower()
    value = PROVIDER_ALIASES.get(value, value)
    return value if value in PROVIDERS else "openai"


def route_provider(route: str = "default") -> str:
    route_key = (route or "default").strip().upper()
    explicit = getattr(settings, f"AI_{route_key}_PROVIDER", "")
    provider = explicit or settings.AI_DEFAULT_PROVIDER or settings.AI_PROVIDER or "openai"
    return normalize_provider(provider)


def _mlapi_models() -> dict[str, dict]:
    raw = (settings.MLAPI_MODELS_JSON or "").strip()
    catalog: dict[str, dict] = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("MLAPI_MODELS_JSON bukan JSON yang valid") from exc
        if not isinstance(parsed, dict):
            raise ValueError("MLAPI_MODELS_JSON harus berupa JSON object")
        for model_id, value in parsed.items():
            if isinstance(value, str):
                catalog[str(model_id)] = {
                    "label": str(model_id),
                    "url": value,
                }
            elif isinstance(value, dict) and value.get("url"):
                catalog[str(model_id)] = {
                    "label": str(value.get("label") or model_id),
                    "url": str(value["url"]),
                    "payload_style": str(
                        value.get("payload_style") or settings.MLAPI_PAYLOAD_STYLE
                    ),
                    "include_model": bool(
                        value.get("include_model", settings.MLAPI_INCLUDE_MODEL)
                    ),
                    "request_model": str(value.get("request_model") or model_id),
                }
    if not catalog and settings.MLAPI_BASE_URL:
        model_id = settings.MLAPI_MODEL or "nemotron-3-ultra"
        catalog[model_id] = {
            "label": model_id,
            "url": settings.MLAPI_BASE_URL,
            "payload_style": settings.MLAPI_PAYLOAD_STYLE,
            "include_model": settings.MLAPI_INCLUDE_MODEL,
            "request_model": model_id,
        }
    return catalog


def route_config(
    route: str = "default",
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> dict:
    route_key = (route or "default").strip().upper()
    provider = normalize_provider(provider_override) if provider_override else route_provider(route)
    default_provider = normalize_provider(settings.AI_DEFAULT_PROVIDER or settings.AI_PROVIDER or "openai")
    fallback_provider = normalize_provider(settings.AI_FALLBACK_PROVIDER or "openai")

    candidates = [provider]
    if not provider_override and route_key not in {"VISION"}:
        candidates.extend([default_provider, fallback_provider, "openai"])

    resolved = None
    for candidate in dict.fromkeys(candidates):
        provider_config = PROVIDERS[candidate]
        api_key = getattr(settings, provider_config["key"], "") or settings.AI_API_KEY
        if candidate == "openai":
            api_key = api_key or settings.OPENAI_API_KEY

        use_route_model = candidate == provider
        route_model = getattr(settings, f"AI_{route_key}_MODEL", "") if use_route_model else ""
        provider_model = getattr(settings, provider_config["model"], "")
        default_model = settings.AI_DEFAULT_MODEL if candidate == default_provider else ""
        fallback_model = settings.AI_FALLBACK_MODEL if candidate == fallback_provider else ""
        model = (
            model_override
            or route_model
            or provider_model
            or settings.AI_MODEL
            or default_model
            or fallback_model
            or provider_config["default_model"]
        )
        max_tokens = getattr(settings, f"AI_{route_key}_MAX_TOKENS", 0) or settings.AI_MAX_TOKENS
        base_url = getattr(settings, provider_config["base_url"], "") or settings.AI_BASE_URL

        mlapi_entry = None
        if candidate == "mlapi":
            catalog = _mlapi_models()
            if model_override and model_override not in catalog:
                raise ValueError(f"Model MLAPI '{model_override}' tidak tersedia di katalog server")
            selected_model = model_override or model
            if selected_model not in catalog and catalog:
                selected_model = next(iter(catalog))
            mlapi_entry = catalog.get(selected_model)
            model = selected_model
            if mlapi_entry:
                base_url = mlapi_entry["url"]
        elif model_override and model_override != provider_model:
            raise ValueError(
                f"Model '{model_override}' tidak tersedia untuk provider {candidate}"
            )

        if candidate in LOCAL_PROVIDERS and settings.AI_LOCAL_ENABLED and base_url:
            api_key = api_key or "local-llm"

        current = {
            "provider": candidate,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "max_tokens": max_tokens,
            "driver": provider_config.get("driver", "openai_compatible"),
        }
        if candidate == "mlapi":
            current.update({
                "payload_style": (
                    mlapi_entry.get("payload_style")
                    if mlapi_entry else settings.MLAPI_PAYLOAD_STYLE
                ),
                "include_model": (
                    mlapi_entry.get("include_model")
                    if mlapi_entry else settings.MLAPI_INCLUDE_MODEL
                ),
                "request_model": (
                    mlapi_entry.get("request_model") if mlapi_entry else model
                ),
                "extra_payload_json": settings.MLAPI_EXTRA_PAYLOAD_JSON,
            })
        if resolved is None:
            resolved = current
        if api_key:
            return current

    return resolved


def available_models() -> list[dict]:
    """Return model choices without exposing API keys or endpoint secrets."""
    choices: list[dict] = []
    for provider, config in PROVIDERS.items():
        api_key = getattr(settings, config["key"], "") or settings.AI_API_KEY
        base_url = getattr(settings, config["base_url"], "") or settings.AI_BASE_URL
        if provider in LOCAL_PROVIDERS and settings.AI_LOCAL_ENABLED and base_url:
            api_key = api_key or "local-llm"
        if not api_key:
            continue
        if provider == "mlapi":
            for model_id, entry in _mlapi_models().items():
                choices.append({
                    "id": f"mlapi:{model_id}",
                    "provider": "mlapi",
                    "model": model_id,
                    "label": entry.get("label") or model_id,
                    "driver": "mlapi",
                })
            continue
        model = getattr(settings, config["model"], "") or config["default_model"]
        choices.append({
            "id": f"{provider}:{model}",
            "provider": provider,
            "model": model,
            "label": f"{provider.upper()} · {model}",
            "driver": config.get("driver", "openai_compatible"),
        })
    return choices


def is_configured(route: str = "default") -> bool:
    return bool(route_config(route)["api_key"])


def local_status() -> dict:
    provider = normalize_provider(settings.AI_LOCAL_PROVIDER)
    if provider not in LOCAL_PROVIDERS:
        provider = "ollama"
    config = PROVIDERS[provider]
    base_url = getattr(settings, config["base_url"], "")
    model = getattr(settings, config["model"], "") or config["default_model"]
    return {
        "enabled": settings.AI_LOCAL_ENABLED,
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "configured": bool(settings.AI_LOCAL_ENABLED and base_url),
    }
