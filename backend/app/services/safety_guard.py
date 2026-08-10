"""
AI safety guard for PMIS.

Guard lokal ini bukan pengganti penuh model content-safety, tetapi sudah memberi
lapisan enforcement sebelum/selepas AI menjawab. Nantinya dapat diganti atau
ditambah dengan Nemotron Content Safety/NVIDIA safety endpoint.
"""
import re
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


@dataclass
class SafetyResult:
    allowed: bool
    reason: str = ""
    category: str = "ok"


PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|system) instructions",
    r"abaikan (instruksi|perintah|aturan)",
    r"bypass",
    r"jailbreak",
    r"developer message",
    r"system prompt",
    r"show.*(prompt|instruction|api key|token|secret)",
    r"tampilkan.*(prompt|instruksi|api key|token|secret)",
]

SECRET_PATTERNS = [
    r"\b(api[_ -]?key|secret|token|password|credential|private key)\b",
    r"\b(env|\.env)\b",
]

OUT_OF_SCOPE_PATTERNS = [
    r"semua proyek",
    r"proyek lain",
    r"perusahaan lain",
    r"tenant lain",
    r"all projects",
    r"other tenant",
]


def _matches(text: str, patterns: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns)


def check_user_question(question: str) -> SafetyResult:
    if not settings.AI_SAFETY_ENABLED:
        return SafetyResult(True)
    if _matches(question, PROMPT_INJECTION_PATTERNS):
        return SafetyResult(
            False,
            "Pertanyaan terdeteksi mencoba mengubah instruksi sistem atau membuka prompt internal.",
            "prompt_injection",
        )
    if _matches(question, SECRET_PATTERNS):
        return SafetyResult(
            False,
            "Permintaan rahasia sistem, token, credential, atau konfigurasi tidak diizinkan.",
            "secret_exfiltration",
        )
    if _matches(question, OUT_OF_SCOPE_PATTERNS):
        return SafetyResult(
            False,
            "Pertanyaan harus dibatasi pada proyek dan dokumen yang sedang dipilih.",
            "cross_scope",
        )
    return SafetyResult(True)


def check_ai_output(answer: str, has_sources: bool = True) -> SafetyResult:
    if not settings.AI_SAFETY_ENABLED:
        return SafetyResult(True)
    if _matches(answer, SECRET_PATTERNS):
        return SafetyResult(
            False,
            "Jawaban berpotensi membocorkan credential atau konfigurasi sensitif.",
            "secret_exfiltration",
        )
    if has_sources and re.search(r"\bmenurut pengetahuan umum\b|\bsecara umum\b", answer or "", re.IGNORECASE):
        return SafetyResult(
            False,
            "Jawaban terlalu bergantung pada pengetahuan umum dan bukan sumber dokumen proyek.",
            "unsupported_answer",
        )
    return SafetyResult(True)


def refusal_message(result: SafetyResult, context: Optional[str] = None) -> str:
    detail = f" {context.strip()}" if context else ""
    return (
        f"Permintaan tidak dapat diproses: {result.reason}{detail} "
        "Silakan ajukan pertanyaan yang spesifik pada dokumen proyek yang tersedia."
    )
