from app.core.config import settings
from app.services.ai_provider_routing import local_status, route_config


def test_ollama_local_provider_is_configured_without_external_api_key(monkeypatch):
    monkeypatch.setattr(settings, "AI_LOCAL_ENABLED", True)
    monkeypatch.setattr(settings, "AI_DEFAULT_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "AI_DEFAULT_MODEL", "qwen3:8b")
    monkeypatch.setattr(settings, "AI_PROVIDER", "")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    monkeypatch.setattr(settings, "AI_FALLBACK_PROVIDER", "")
    monkeypatch.setattr(settings, "OLLAMA_API_KEY", "")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "qwen3:8b")

    config = route_config("default")

    assert config["provider"] == "ollama"
    assert config["api_key"] == "local-llm"
    assert config["base_url"] == "http://ollama:11434/v1"
    assert config["model"] == "qwen3:8b"


def test_local_status_reports_selected_provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_LOCAL_ENABLED", True)
    monkeypatch.setattr(settings, "AI_LOCAL_PROVIDER", "vllm")
    monkeypatch.setattr(settings, "VLLM_BASE_URL", "http://vllm:8000/v1")
    monkeypatch.setattr(settings, "VLLM_MODEL", "Qwen/Qwen3-14B")

    status = local_status()

    assert status["enabled"] is True
    assert status["provider"] == "vllm"
    assert status["configured"] is True
    assert status["model"] == "Qwen/Qwen3-14B"
