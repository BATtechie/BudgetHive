import logging
from typing import List, Optional

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


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
):
    config_kwargs = {
        "system_instruction": system_instruction,
        "response_mime_type": response_mime_type,
        "temperature": temperature,
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
        except Exception as exc:  # pragma: no cover - exercised in runtime
            last_error = exc
            logger.warning("Gemini call failed with model %s: %s", model_name, exc)

    raise RuntimeError("All Gemini model attempts failed") from last_error
