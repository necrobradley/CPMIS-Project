import pytest

from app.core.config import settings
from app.services.ai_provider_routing import available_models, route_config
from app.services.ai_service import AIService
from app.services.mlapi_provider import build_payload, extract_text


def test_build_payload_uses_conversation_messages_by_default():
    payload = build_payload(
        system_prompt="Kamu asisten proyek.",
        user_message="Ringkas progres hari ini.",
        model="nemotron-3-ultra",
        temperature=0.2,
        max_tokens=512,
        payload_style="messages",
        include_model=False,
    )

    assert payload["messages"] == [
        {"role": "system", "content": "Kamu asisten proyek."},
        {"role": "user", "content": "Ringkas progres hari ini."},
    ]
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 512
    assert "model" not in payload


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"choices": [{"message": {"content": "Jawaban OpenAI"}}]}, "Jawaban OpenAI"),
        ({"output": {"text": "Jawaban output"}}, "Jawaban output"),
        ({"generated_text": "Jawaban generated"}, "Jawaban generated"),
        ({"result": [{"text": "Jawaban list"}]}, "Jawaban list"),
    ],
)
def test_extract_text_supports_common_serverless_responses(response, expected):
    assert extract_text(response) == expected


def test_extract_text_rejects_unknown_response_shape():
    with pytest.raises(ValueError, match="format respons"):
        extract_text({"unknown": {"value": 1}})


def test_mlapi_catalog_routes_multiple_models_with_one_key(monkeypatch):
    monkeypatch.setattr(settings, "MLAPI_API_KEY", "shared-key")
    monkeypatch.setattr(settings, "MLAPI_BASE_URL", "")
    monkeypatch.setattr(settings, "MLAPI_MODEL", "nemotron-3-ultra")
    monkeypatch.setattr(
        settings,
        "MLAPI_MODELS_JSON",
        '{"nemotron-3-ultra":{"label":"Nemotron 3 Ultra","url":"https://mlapi.run/nemotron"},'
        '"model-kedua":{"label":"Model Kedua","url":"https://mlapi.run/model-kedua"}}',
    )

    config = route_config(
        "default",
        provider_override="mlapi",
        model_override="model-kedua",
    )

    assert config["provider"] == "mlapi"
    assert config["driver"] == "mlapi"
    assert config["model"] == "model-kedua"
    assert config["base_url"] == "https://mlapi.run/model-kedua"
    assert config["api_key"] == "shared-key"
    assert {item["id"] for item in available_models()} >= {
        "mlapi:nemotron-3-ultra",
        "mlapi:model-kedua",
    }


def test_mlapi_rejects_model_outside_server_catalog(monkeypatch):
    monkeypatch.setattr(settings, "MLAPI_API_KEY", "shared-key")
    monkeypatch.setattr(settings, "MLAPI_MODELS_JSON", '{"allowed":"https://mlapi.run/allowed"}')

    with pytest.raises(ValueError, match="tidak tersedia"):
        route_config("default", provider_override="mlapi", model_override="not-allowed")


@pytest.mark.asyncio
async def test_ai_service_dispatches_selected_mlapi_model(monkeypatch):
    monkeypatch.setattr(settings, "MLAPI_API_KEY", "shared-key")
    monkeypatch.setattr(
        settings,
        "MLAPI_MODELS_JSON",
        '{"nemotron-3-ultra":{"url":"https://mlapi.run/nemotron","label":"Nemotron 3 Ultra"}}',
    )
    captured = {}

    async def fake_chat_completion(**kwargs):
        captured.update(kwargs)
        return "Respons Nemotron"

    monkeypatch.setattr(
        "app.services.ai_service.mlapi_provider.chat_completion",
        fake_chat_completion,
    )

    response = await AIService().chat(
        "Apa status proyek?",
        provider="mlapi",
        model="nemotron-3-ultra",
    )

    assert response == "Respons Nemotron"
    assert captured["url"] == "https://mlapi.run/nemotron"
    assert captured["api_key"] == "shared-key"
    assert captured["user_message"] == "Apa status proyek?"
