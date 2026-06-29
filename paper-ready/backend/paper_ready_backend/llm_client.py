"""OpenAI-compatible LLM client boundary with local fallbacks."""

from __future__ import annotations

import json
import re
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


def complete_json_with_web_search(
    settings: AppSettings,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any] | None:
    """Call Responses API with model-managed web search and parse JSON."""
    if not has_llm_credentials(settings):
        return None
    try:
        client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.llm_api_base_url,
        )
        response = client.responses.create(
            model=model_id,
            tools=[{"type": "web_search"}],
            input=f"{system_prompt}\n\n{user_prompt}",
        )
        return _parse_json_text(response.output_text)
    except Exception:
        return _complete_json_with_preview_web_search(
            settings, model_id, system_prompt, user_prompt
        )


def estimate_tokens(text: str) -> int:
    """Estimate tokens cheaply for budget checks before provider calls."""
    return max(1, len(text) // 4)


def _complete_json_with_preview_web_search(
    settings: AppSettings,
    model_id: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any] | None:
    """Retry with the preview web-search tool name for older SDK/API support."""
    try:
        client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.llm_api_base_url,
        )
        response = client.responses.create(
            model=model_id,
            tools=[{"type": "web_search_preview"}],
            input=f"{system_prompt}\n\n{user_prompt}",
        )
        return _parse_json_text(response.output_text)
    except Exception:
        return None


def _parse_json_text(text: str | None) -> dict[str, Any] | None:
    """Parse a JSON object from a model response."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
