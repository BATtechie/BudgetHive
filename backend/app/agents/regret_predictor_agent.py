"""
A5 — Regret Predictor Agent

Predicts likelihood the user will regret a purchase based on:
  - Purchase history patterns (check-in data, regret scores, return/resold rates)
  - Financial agent output
  - Need agent output
  - Item price/category

When no history exists, falls back to weighted formula from financial + need scores.
Never fabricates historical patterns.
"""

import json
import logging
from enum import Enum
from typing import List, Optional

from google import genai
from pydantic import BaseModel, Field

from app.config import settings
from app.agents.llm_utils import generate_content_with_fallback

logger = logging.getLogger(__name__)


class RegretRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RegretPrediction(BaseModel):
    regret_score: float = Field(..., ge=0, le=100, description="0 = no regret expected, 100 = very likely to regret.")
    risk_level: RegretRiskLevel
    reasons: List[str] = Field(..., description="Key factors driving the regret prediction.")
    confidence: float = Field(..., ge=0, le=100, description="Confidence in this prediction.")
    data_source: str = Field(..., description="'HISTORY_AND_LLM', 'FORMULA_FALLBACK', or 'LLM_ONLY'.")


def _classify_risk(score: float) -> RegretRiskLevel:
    if score >= 65:
        return RegretRiskLevel.HIGH
    if score >= 35:
        return RegretRiskLevel.MEDIUM
    return RegretRiskLevel.LOW


def _fallback_from_scores(
    financial_score: Optional[float],
    need_score: Optional[float],
) -> RegretPrediction:
    fin = financial_score if financial_score is not None else 50.0
    need = need_score if need_score is not None else 50.0
    regret = round(100.0 - (0.6 * fin + 0.4 * need), 1)
    regret = max(0.0, min(100.0, regret))

    reasons = []
    if fin < 40:
        reasons.append("Purchase strains the financial budget.")
    if need < 40:
        reasons.append("Low assessed need for this product.")
    if fin >= 70 and need >= 70:
        reasons.append("Both financial and need signals are positive — low regret expected.")
    if not reasons:
        reasons.append("Moderate financial and need signals — some regret risk.")

    return RegretPrediction(
        regret_score=regret,
        risk_level=_classify_risk(regret),
        reasons=reasons,
        confidence=40.0,
        data_source="FORMULA_FALLBACK",
    )


_REGRET_SYSTEM_PROMPT = """
You are the BudgetHive Regret Predictor Agent.

Your job is to predict how likely the user is to regret this purchase.
You receive the user's purchase history patterns (if available), financial assessment,
need assessment, and product details.

Return only valid JSON with these exact fields:
  regret_score (0-100, where 100 = very likely to regret),
  risk_level ("LOW", "MEDIUM", or "HIGH"),
  reasons (list of 2-4 short strings explaining the prediction),
  confidence (0-100),
  data_source (always "HISTORY_AND_LLM" when history is provided, "LLM_ONLY" otherwise)

Do not fabricate or invent purchase history patterns. Only reference data actually provided.
Do not include any markdown or extra text.
""".strip()


def _get_client() -> Optional[genai.Client]:
    key = settings.GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not configured.")
        return None
    return genai.Client(api_key=key)


def predict_regret(
    product_name: str,
    category: str,
    price: float,
    financial_score: Optional[float] = None,
    need_score: Optional[float] = None,
    history_summary: Optional[str] = None,
) -> RegretPrediction:
    client = _get_client()
    if client is None:
        return _fallback_from_scores(financial_score, need_score)

    history_block = history_summary or "No purchase history available for this user/category."
    has_history = history_summary is not None and history_summary.strip() != ""

    fin_text = f"{financial_score:.1f}/100" if financial_score is not None else "not available"
    need_text = f"{need_score:.1f}/100" if need_score is not None else "not available"

    prompt = f"""
Predict the likelihood of regret for this purchase.

Product  : {product_name}
Category : {category}
Price    : ₹{price:,.0f}

Financial Agent Score : {fin_text}
Need Agent Score      : {need_text}

Purchase History in this category:
{history_block}

Return JSON in this exact format:
{{
  "regret_score": <number 0-100>,
  "risk_level": <"LOW"|"MEDIUM"|"HIGH">,
  "reasons": ["<reason1>", "<reason2>"],
  "confidence": <number 0-100>,
  "data_source": "{'HISTORY_AND_LLM' if has_history else 'LLM_ONLY'}"
}}
""".strip()

    try:
        response = generate_content_with_fallback(
            client,
            contents=prompt,
            system_instruction=_REGRET_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.3,
        )
        data = json.loads(response.text.strip())
        data["regret_score"] = round(max(0.0, min(100.0, float(data["regret_score"]))), 1)
        data["confidence"] = round(max(0.0, min(100.0, float(data["confidence"]))), 1)
        data["data_source"] = "HISTORY_AND_LLM" if has_history else "LLM_ONLY"
        return RegretPrediction(**data)

    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Regret predictor parse error: %s", exc)
        return _fallback_from_scores(financial_score, need_score)
    except Exception as exc:
        logger.error("Regret predictor error: %s", exc)
        return _fallback_from_scores(financial_score, need_score)
