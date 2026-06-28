"""OpenAI-compatible LLM client boundary with local fallbacks."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .models import AppSettings


def has_llm_credentials(settings: AppSettings) -> bool:
    """Return whether settings can make a provider-backed LLM request."""
    return bool(settings.api_key and settings.api_key.strip())


def complete_json(
    settings: AppSettings,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any] | None:
    """Call an OpenAI-compatible chat endpoint and parse a JSON response."""
    if not has_llm_credentials(settings):
        return None
    try:
        client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.llm_api_base_url,
        )
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    """Estimate tokens cheaply for budget checks before provider calls."""
    return max(1, len(text) // 4)
