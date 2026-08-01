import logging
from typing import List, Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_JSON_MAX_TOKENS = 1024
_DEFAULT_GROUNDED_MAX_TOKENS = 800


def _get_model_candidates() -> List[str]:
    configured = [item.strip() for item in settings.GEMINI_MODEL.split(",") if item.strip()]
    fallback_models = [
        item.strip()
        for item in getattr(settings, "GEMINI_MODEL_FALLBACKS", "").split(",")
        if item.strip()
    ]
    candidates = configured + fallback_models
    if not candidates:
        candidates = ["gemini-2.0-flash"]
    return candidates


def generate_content_with_fallback(
    client: genai.Client,
    *,
    contents: str,
    system_instruction: str,
    response_mime_type: str = "application/json",
    temperature: float = 0.2,
    thinking_budget: Optional[int] = None,
    max_output_tokens: int = _DEFAULT_JSON_MAX_TOKENS,
):
    config_kwargs = {
        "system_instruction": system_instruction,
        "response_mime_type": response_mime_type,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if thinking_budget is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

    last_error = None
    for model_name in _get_model_candidates():
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini call failed with model %s: %s", model_name, exc)

    raise RuntimeError("All Gemini model attempts failed") from last_error


def generate_grounded_content(
    client: genai.Client,
    *,
    contents: str,
    system_instruction: str,
    temperature: float = 0.2,
    max_output_tokens: int = _DEFAULT_GROUNDED_MAX_TOKENS,
) -> str:
    config_kwargs = {
        "system_instruction": system_instruction,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "tools": [types.Tool(google_search=types.GoogleSearch())],
    }

    last_error = None
    for model_name in _get_model_candidates():
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            return response.text
        except Exception as exc:
            last_error = exc
            logger.warning("Grounded Gemini call failed with model %s: %s", model_name, exc)

    raise RuntimeError("All grounded Gemini attempts failed") from last_error