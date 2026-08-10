"""Secure AI gateway for external LLM calls.

The gateway keeps project documents local, sends only the caller-provided prompt,
and masks sensitive values before they leave the backend. It is intentionally
provider-agnostic so every OpenAI-compatible route can pass through the same
controls.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from app.core.config import settings


MASK_PATTERN = re.compile(r"\[(EMAIL|PHONE|TELEGRAM|MONEY|SECRET|COMPANY|PROJECT)_[0-9]+\]")


@dataclass
class GatewayDecision:
    allowed: bool
    system_prompt: str
    user_message: str
    policy: str
    sensitivity: str
    categories: List[str] = field(default_factory=list)
    replacements: Dict[str, str] = field(default_factory=dict)
    reason: str = ""
    original_chars: int = 0
    outbound_chars: int = 0


class SecureAIGateway:
    SECRET_PATTERNS = [
        (r"\bsk-[A-Za-z0-9_\-]{16,}\b", "SECRET"),
        (r"\b(api[_ -]?key|secret|private key|password|credential)\s*[:=]\s*['\"]?[^'\"\s]{6,}", "SECRET"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----", "SECRET"),
    ]
    PII_PATTERNS = [
        (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "EMAIL"),
        (r"(?<!\w)(?:\+?62|0)[\d\s\-().]{8,16}\d(?!\w)", "PHONE"),
        (r"\btelegram(?:\s+id)?\s*[:#-]?\s*\d{6,15}\b", "TELEGRAM"),
    ]
    COMMERCIAL_PATTERNS = [
        (r"\b(?:Rp|IDR|USD|US\$|\$)\s?[\d.,]+(?:\s?(?:miliar|juta|ribu|billion|million))?\b", "MONEY"),
        (r"\b(?:PT|CV)\s+[A-Z][A-Za-z0-9&.,'\- ]{2,60}", "COMPANY"),
        (r"\b(?:Proyek|Project)\s+[A-Z0-9][A-Za-z0-9&.,'\- ]{2,80}", "PROJECT"),
    ]

    def __init__(self):
        self.policy = (settings.AI_GATEWAY_EXTERNAL_SENSITIVE_POLICY or "mask").strip().lower()

    def prepare(self, system_prompt: str, user_message: str, route: str = "default") -> GatewayDecision:
        original = f"{system_prompt}\n{user_message}"
        original_chars = len(original)
        categories = self.classify(original)

        if not settings.AI_GATEWAY_ENABLED:
            return GatewayDecision(
                allowed=True,
                system_prompt=system_prompt,
                user_message=user_message,
                policy="disabled",
                sensitivity=self.sensitivity(categories),
                categories=categories,
                original_chars=original_chars,
                outbound_chars=original_chars,
            )

        if original_chars > settings.AI_GATEWAY_MAX_PROMPT_CHARS:
            return GatewayDecision(
                allowed=False,
                system_prompt="",
                user_message="",
                policy=self.policy,
                sensitivity="high",
                categories=categories + ["oversized_prompt"],
                reason=f"Prompt melebihi batas aman {settings.AI_GATEWAY_MAX_PROMPT_CHARS} karakter untuk API eksternal.",
                original_chars=original_chars,
                outbound_chars=0,
            )

        if self.policy == "block" and categories:
            return GatewayDecision(
                allowed=False,
                system_prompt="",
                user_message="",
                policy=self.policy,
                sensitivity=self.sensitivity(categories),
                categories=categories,
                reason="Data sensitif terdeteksi dan policy gateway memblokir pengiriman ke API eksternal.",
                original_chars=original_chars,
                outbound_chars=0,
            )

        if self.policy == "allow":
            return GatewayDecision(
                allowed=True,
                system_prompt=system_prompt,
                user_message=user_message,
                policy=self.policy,
                sensitivity=self.sensitivity(categories),
                categories=categories,
                original_chars=original_chars,
                outbound_chars=original_chars,
            )

        masked_system, replacements = self.mask(system_prompt)
        masked_user, user_replacements = self.mask(user_message, existing=replacements)
        replacements.update(user_replacements)
        return GatewayDecision(
            allowed=True,
            system_prompt=masked_system,
            user_message=masked_user,
            policy="mask",
            sensitivity=self.sensitivity(categories),
            categories=categories,
            replacements=replacements,
            original_chars=original_chars,
            outbound_chars=len(masked_system) + len(masked_user),
        )

    def restore(self, text: str, decision: GatewayDecision) -> str:
        if not text or not decision.replacements:
            return text
        restored = text
        for placeholder, original in decision.replacements.items():
            restored = restored.replace(placeholder, original)
        return restored

    def classify(self, text: str) -> List[str]:
        categories = []
        for pattern, category in self._active_patterns():
            if re.search(pattern, text or "", flags=re.IGNORECASE):
                categories.append(category.lower())
        return sorted(set(categories))

    @staticmethod
    def sensitivity(categories: List[str]) -> str:
        if any(item in categories for item in ("secret", "money")):
            return "high"
        if categories:
            return "medium"
        return "low"

    def mask(self, text: str, existing: Dict[str, str] | None = None) -> tuple[str, Dict[str, str]]:
        replacements = dict(existing or {})
        reverse = {value: key for key, value in replacements.items()}
        masked = text or ""
        counters: Dict[str, int] = {}
        for placeholder in replacements:
            match = MASK_PATTERN.fullmatch(placeholder)
            if match:
                counters[match.group(1)] = max(counters.get(match.group(1), 0), int(placeholder.rsplit("_", 1)[1][:-1]))

        for pattern, category in self._active_patterns():
            def replace(match):
                original = match.group(0)
                if original in reverse:
                    return reverse[original]
                counters[category] = counters.get(category, 0) + 1
                placeholder = f"[{category}_{counters[category]}]"
                replacements[placeholder] = original
                reverse[original] = placeholder
                return placeholder

            masked = re.sub(pattern, replace, masked, flags=re.IGNORECASE)
        return masked, replacements

    def _active_patterns(self):
        patterns = list(self.SECRET_PATTERNS) + list(self.PII_PATTERNS)
        commercial = []
        for pattern, category in self.COMMERCIAL_PATTERNS:
            if category == "MONEY" and not settings.AI_GATEWAY_MASK_FINANCIAL:
                continue
            commercial.append((pattern, category))
        return patterns + commercial


secure_ai_gateway = SecureAIGateway()
