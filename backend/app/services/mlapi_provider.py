"""Adapter untuk endpoint model serverless bergaya ``mlapi.run``.

Endpoint pada model library menggunakan satu URL per model dan autentikasi
Bearer. Bentuk respons dapat berbeda antar deployment, sehingga adapter ini
mendukung beberapa envelope respons yang umum tanpa pernah mengekspos API key
ke frontend.
"""
from __future__ import annotations

import json
from typing import Any

import httpx


def build_payload(
    *,
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float,
    max_tokens: int,
    payload_style: str = "messages",
    include_model: bool = False,
    extra_payload_json: str = "",
) -> dict[str, Any]:
    """Bangun payload untuk model serverless yang dipilih."""
    style = (payload_style or "messages").strip().lower()
    if style == "prompt":
        payload: dict[str, Any] = {
            "prompt": f"System:\n{system_prompt}\n\nUser:\n{user_message}",
        }
    elif style == "input":
        payload = {
            "input": {
                "system": system_prompt,
                "prompt": user_message,
            },
        }
    else:
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

    payload["temperature"] = temperature
    payload["max_tokens"] = max_tokens
    if include_model and model:
        payload["model"] = model

    if extra_payload_json:
        try:
            extra = json.loads(extra_payload_json)
        except json.JSONDecodeError as exc:
            raise ValueError("MLAPI_EXTRA_PAYLOAD_JSON bukan JSON yang valid") from exc
        if not isinstance(extra, dict):
            raise ValueError("MLAPI_EXTRA_PAYLOAD_JSON harus berupa JSON object")
        payload.update(extra)
    return payload


def _at_path(value: Any, *path: str | int) -> Any:
    current = value
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, list) or len(current) <= part:
                return None
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
    return current


def extract_text(response: Any) -> str:
    """Ambil teks dari envelope respons model serverless yang umum."""
    if isinstance(response, str) and response.strip():
        return response.strip()

    paths = (
        ("choices", 0, "message", "content"),
        ("choices", 0, "text"),
        ("output", "text"),
        ("output", "content"),
        ("result", "text"),
        ("result", 0, "text"),
        ("data", "text"),
        ("generated_text",),
        ("response",),
        ("text",),
    )
    for path in paths:
        candidate = _at_path(response, *path)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, list):
            text_parts = [item for item in candidate if isinstance(item, str) and item.strip()]
            if text_parts:
                return "".join(text_parts).strip()

    raise ValueError(
        "Model serverless merespons, tetapi format respons belum dikenali. "
        "Periksa MLAPI_PAYLOAD_STYLE atau sesuaikan adapter respons."
    )


async def chat_completion(
    *,
    url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    payload_style: str = "messages",
    include_model: bool = False,
    extra_payload_json: str = "",
) -> str:
    if not url:
        raise ValueError("MLAPI_BASE_URL atau URL model MLAPI belum dikonfigurasi")
    if not api_key:
        raise ValueError("MLAPI_API_KEY belum dikonfigurasi")

    payload = build_payload(
        system_prompt=system_prompt,
        user_message=user_message,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        payload_style=payload_style,
        include_model=include_model,
        extra_payload_json=extra_payload_json,
    )
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text[:500]
        raise ValueError(
            f"Model serverless gagal ({response.status_code}): {detail}"
        ) from exc

    content_type = response.headers.get("content-type", "")
    body: Any = response.json() if "json" in content_type else response.text
    return extract_text(body)
