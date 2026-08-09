from app.core.config import settings
from app.services.secure_ai_gateway import SecureAIGateway


def test_secure_ai_gateway_masks_sensitive_project_data(monkeypatch):
    monkeypatch.setattr(settings, "AI_GATEWAY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY", "mask")
    monkeypatch.setattr(settings, "AI_GATEWAY_MASK_FINANCIAL", True)
    monkeypatch.setattr(settings, "AI_GATEWAY_MAX_PROMPT_CHARS", 24000)

    gateway = SecureAIGateway()
    decision = gateway.prepare(
        "Jawab hanya dari dokumen.",
        "PT Aman Karya mengerjakan Proyek Bandara Alpha senilai Rp 42.500.000.000. Hubungi pm@aman.co.id atau 081234567890.",
        route="analysis",
    )

    assert decision.allowed is True
    assert decision.policy == "mask"
    assert decision.sensitivity == "high"
    assert "money" in decision.categories
    assert "email" in decision.categories
    assert "Rp 42.500.000.000" not in decision.user_message
    assert "pm@aman.co.id" not in decision.user_message
    assert "[MONEY_1]" in decision.user_message
    assert "[EMAIL_1]" in decision.user_message

    restored = gateway.restore("Nilai kontrak [MONEY_1], kontak [EMAIL_1].", decision)
    assert "Rp 42.500.000.000" in restored
    assert "pm@aman.co.id" in restored


def test_secure_ai_gateway_blocks_sensitive_data_when_policy_block(monkeypatch):
    monkeypatch.setattr(settings, "AI_GATEWAY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY", "block")
    monkeypatch.setattr(settings, "AI_GATEWAY_MASK_FINANCIAL", True)
    monkeypatch.setattr(settings, "AI_GATEWAY_MAX_PROMPT_CHARS", 24000)

    gateway = SecureAIGateway()
    decision = gateway.prepare(
        "Analisis dokumen.",
        "Dokumen berisi api_key=super-secret-token dan nilai Rp 10.000.000.",
        route="default",
    )

    assert decision.allowed is False
    assert decision.sensitivity == "high"
    assert "secret" in decision.categories


def test_secure_ai_gateway_blocks_oversized_prompt(monkeypatch):
    monkeypatch.setattr(settings, "AI_GATEWAY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY", "mask")
    monkeypatch.setattr(settings, "AI_GATEWAY_MAX_PROMPT_CHARS", 20)

    gateway = SecureAIGateway()
    decision = gateway.prepare("system", "x" * 30)

    assert decision.allowed is False
    assert "oversized_prompt" in decision.categories
