"""
A4 — Alternatives Agent
"""

import json
import logging
from enum import Enum
from typing import List, Optional

from google import genai
from pydantic import BaseModel, Field

from app.config import settings
from app.agents.llm_utils import generate_content_with_fallback, generate_grounded_content

logger = logging.getLogger(__name__)


class AlternativeType(str, Enum):
    CHEAPER_SAME_SPEC = "CHEAPER_SAME_SPEC"
    REFURBISHED = "REFURBISHED"
    DIFFERENT_BRAND = "DIFFERENT_BRAND"


class Alternative(BaseModel):
    product_name: str = Field(..., description="Name of the alternative product.")
    price: float = Field(..., description="Price of the alternative in INR.")
    savings_amount: float = Field(..., description="Amount saved vs the original product price.")
    spec_difference: str = Field(..., description="One-line summary of key spec differences, if any.")
    alternative_type: AlternativeType


class AlternativesEvaluation(BaseModel):
    score: float = Field(
        ..., ge=0, le=100,
        description="100 = no good alternative exists. Lower = a strong alternative undercuts the original.",
    )
    alternatives: List[Alternative] = Field(default_factory=list)
    reasoning: str = Field(..., description="One sentence summarising the strongest alternative found, if any.")
    data_source: str = Field(..., description="'LLM' or 'FALLBACK'.")


_FALLBACK_EVALUATION = AlternativesEvaluation(
    score=70.0,
    alternatives=[],
    reasoning="Could not reach the AI model — no alternatives could be searched.",
    data_source="FALLBACK",
)

_SEARCH_SYSTEM_PROMPT = """
You are a shopping research assistant for BudgetHive.
Search Amazon India, Flipkart, Croma, and Reliance Digital for real
alternatives to a given product. Only report prices/products you actually
find via search — never invent numbers. Be concise.
""".strip()

_STRUCTURE_SYSTEM_PROMPT = """
You are the Alternatives Agent for BudgetHive, an AI purchase decision assistant.

You receive real search findings about alternative products. Structure them
into the required JSON schema.

Scoring guide:
  - Strong alternative saves significant money, minimal trade-off → score LOW (0-40).
  - Alternatives exist but meaningfully worse → score MODERATE (41-70).
  - No good alternative found → score HIGH (71-100).

Critical rules:
- Use ONLY prices/products mentioned in the findings — never invent any.
- If findings contain no real alternatives, return an empty alternatives list and score HIGH.
- Return ONLY valid JSON. No markdown. No extra text.
""".strip()


def _get_client() -> Optional[genai.Client]:
    key = settings.GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not configured.")
        return None
    return genai.Client(api_key=key)


def run_alternatives_agent(
    product_name: str,
    category: str,
    price: float,
    budget_ceiling: Optional[float] = None,
    primary_use_case: Optional[str] = None,
) -> AlternativesEvaluation:
    client = _get_client()
    if client is None:
        return _FALLBACK_EVALUATION

    # STEP 1 — real web search via grounding
    search_prompt = f"""
Find 2-3 real alternatives to "{product_name}" ({category}, currently ₹{price:,.0f}).
Prioritise: (a) lower price with comparable specs, (b) refurbished/open-box
options, (c) different brand with better value-for-money.
{f"Budget ceiling: ₹{budget_ceiling:,.0f}." if budget_ceiling else ""}
{f"Primary use case: {primary_use_case}." if primary_use_case else ""}
List each with its real current price and one-line spec comparison.
""".strip()

    try:
        grounded_text = generate_grounded_content(
            client,
            contents=search_prompt,
            system_instruction=_SEARCH_SYSTEM_PROMPT,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("run_alternatives_agent — grounded search failed: %s", exc)
        return _FALLBACK_EVALUATION

    # STEP 2 — structure the grounded findings into schema
    structure_prompt = f"""
Original product: {product_name} at ₹{price:,.0f}

Real search findings:
{grounded_text}

Return JSON in this exact format:
{{
  "score": <number 0-100>,
  "alternatives": [
    {{ "product_name": "<name>", "price": <number>, "savings_amount": <number>,
       "spec_difference": "<one line>", "alternative_type": <"CHEAPER_SAME_SPEC"|"REFURBISHED"|"DIFFERENT_BRAND"> }}
  ],
  "reasoning": "<one sentence>",
  "data_source": "LLM"
}}
""".strip()

    try:
        response = generate_content_with_fallback(
            client,
            contents=structure_prompt,
            system_instruction=_STRUCTURE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.1,
        )
        data = json.loads(response.text.strip())
        data["score"] = round(min(max(float(data["score"]), 0.0), 100.0), 1)
        data["data_source"] = "LLM"
        return AlternativesEvaluation(**data)
    except json.JSONDecodeError as exc:
        logger.error("run_alternatives_agent — JSON decode error: %s", exc)
        return _FALLBACK_EVALUATION
    except Exception as exc:
        logger.error("run_alternatives_agent — structuring error: %s", exc)
        return _FALLBACK_EVALUATION