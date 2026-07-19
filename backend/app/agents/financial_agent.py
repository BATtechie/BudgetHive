import json
import logging
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)

# Define the structured output format for the Financial Agent
class FinancialEvaluation(BaseModel):
    score: float = Field(
        ..., 
        ge=0,
        le=100,
        description="Score between 0 and 100. 100 is highly affordable, 0 is unaffordable."
    )
    reasoning: str = Field(
        ..., 
        description="Detailed explanation of the financial impact of this purchase."
    )
    discretionary_income: float = Field(
        ..., 
        description="Remaining money after savings, EMIs, and bills."
    )
    price_to_income_ratio: float = Field(
        ..., 
        description="Percentage of discretionary income consumed by this purchase."
    )
    data_source: str = Field(
        ..., 
        description="The source of this evaluation: RULE_BASED or LLM."
    )


_FINANCE_SYSTEM_PROMPT = """
You are the BudgetHive Financial Agent.

Your job is to assess whether a purchase is financially sensible for the user.
You receive the user's monthly income, monthly savings target, active EMIs, recurring bills, and the purchase price.

Return only valid JSON with the exact fields: score, reasoning, discretionary_income, price_to_income_ratio, data_source.
Do not include any markdown or extra text.
""".strip()


def _get_client() -> Optional[genai.Client]:
    key = settings.GEMINI_API_KEY
    if not key or key == "your_gemini_api_key_here":
        logger.warning("GEMINI_API_KEY not configured.")
        return None
    return genai.Client(api_key=key)


def _deterministic_financials(
    user_income: float,
    savings_target: float,
    emis: float,
    bills: float,
    purchase_price: float,
) -> FinancialEvaluation:
    discretionary_income = user_income - (savings_target + emis + bills)

    if discretionary_income <= 0:
        return FinancialEvaluation(
            score=0.0,
            reasoning="Your fixed expenses and savings targets exceed your monthly income. You have zero discretionary budget.",
            discretionary_income=discretionary_income,
            price_to_income_ratio=0.0,
            data_source="RULE_BASED",
        )

    price_to_income_ratio = (purchase_price / discretionary_income) * 100

    if purchase_price > discretionary_income:
        score = max(0.0, 30.0 - (purchase_price - discretionary_income) / 100)
        reasoning = (
            f"This purchase of {purchase_price} exceeds your monthly discretionary income of {discretionary_income:.2f} "
            f"by {(purchase_price - discretionary_income):.2f}. It will reduce your ability to meet savings goals."
        )
    elif price_to_income_ratio > 50:
        score = 50.0 - (price_to_income_ratio - 50.0) * 0.4
        reasoning = (
            f"This purchase is affordable but takes up {price_to_income_ratio:.1f}% of your discretionary income ({discretionary_income:.2f})."
        )
    elif price_to_income_ratio > 10:
        score = 85.0 - (price_to_income_ratio - 10.0) * 0.5
        reasoning = (
            f"This purchase fits your discretionary budget and consumes {price_to_income_ratio:.1f}% of it."
        )
    else:
        score = 95.0
        reasoning = (
            f"Highly affordable purchase; it consumes only {price_to_income_ratio:.1f}% of your discretionary income."
        )

    score = min(max(score, 0.0), 100.0)
    return FinancialEvaluation(
        score=round(score, 1),
        reasoning=reasoning,
        discretionary_income=round(discretionary_income, 2),
        price_to_income_ratio=round(price_to_income_ratio, 2),
        data_source="RULE_BASED",
    )


def _evaluate_financials_with_llm(
    user_income: float,
    savings_target: float,
    emis: float,
    bills: float,
    purchase_price: float,
) -> FinancialEvaluation:
    client = _get_client()
    if client is None:
        return _deterministic_financials(user_income, savings_target, emis, bills, purchase_price)

    discretionary_income = user_income - (savings_target + emis + bills)
    price_to_income_ratio = (
        (purchase_price / discretionary_income * 100)
        if discretionary_income > 0
        else 0.0
    )

    prompt = f"""
Evaluate this purchase using the values below.

Monthly income: {user_income}
Monthly savings target: {savings_target}
Active EMIs: {emis}
Recurring bills: {bills}
Purchase price: {purchase_price}

Return JSON in this exact format:
{{
  "score": <number 0-100>,
  "reasoning": "<one sentence explaining affordability and risk to savings>",
  "discretionary_income": <number>,
  "price_to_income_ratio": <number>,
  "data_source": "LLM"
}}
""".strip()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_FINANCE_SYSTEM_PROMPT,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=1024,
                ),
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        data = json.loads(response.text.strip())
        
        # Enforce correct computed fields and correct score range
        data["discretionary_income"] = round(discretionary_income, 2)
        data["price_to_income_ratio"] = round(price_to_income_ratio, 2)
        data["data_source"] = "LLM"
        data["score"] = round(min(max(float(data["score"]), 0.0), 100.0), 1)

        return FinancialEvaluation(**data)

    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("LLM finance evaluation parse error: %s", exc)
        return _deterministic_financials(user_income, savings_target, emis, bills, purchase_price)
    except Exception as exc:
        logger.error("LLM finance evaluation error: %s", exc)
        return _deterministic_financials(user_income, savings_target, emis, bills, purchase_price)


def evaluate_financials(
    user_income: float,
    savings_target: float,
    emis: float,
    bills: float,
    purchase_price: float,
    use_llm: bool = False,
) -> FinancialEvaluation:
    """
    Evaluates the financial viability of a purchase.

    If use_llm is True and GEMINI_API_KEY is configured, this returns an LLM-generated reasoning result
    using Gemini 2.5 Flash as a thinking model.
    Otherwise it falls back to the deterministic rule-based evaluator.
    """
    if use_llm:
        return _evaluate_financials_with_llm(user_income, savings_target, emis, bills, purchase_price)
    return _deterministic_financials(user_income, savings_target, emis, bills, purchase_price)
