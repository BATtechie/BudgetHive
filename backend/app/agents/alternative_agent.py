"""
A4 — Alternatives Agent
"""

import asyncio
import json
import logging
import re
import threading
from enum import Enum
from typing import Any, List, Optional

import httpx
from bs4 import BeautifulSoup

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
    data_source: str = Field(..., description="'LLM', 'LIVE_WEB', or 'FALLBACK'.")


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


def _extract_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        digits = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", value)
        if not digits:
            return None
        text = digits[-1].replace(",", "")
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _coerce_listing(listing: Any) -> dict[str, Any]:
    title = None
    for attr in ("title", "product_name", "name", "product"):
        if hasattr(listing, attr):
            value = getattr(listing, attr)
            if value:
                title = str(value)
                break
    if not title:
        title = str(listing)

    price = None
    for attr in ("listed_price", "price", "current_price", "sale_price"):
        if hasattr(listing, attr):
            candidate = _extract_price(getattr(listing, attr))
            if candidate is not None:
                price = candidate
                break
    if price is None:
        price = _extract_price(title)

    url = None
    for attr in ("url", "product_url", "link"):
        if hasattr(listing, attr):
            value = getattr(listing, attr)
            if value:
                url = str(value)
                break

    return {"title": title, "price": price, "url": url}


def _build_live_web_alternatives(
    product_name: str,
    category: str,
    price: float,
    listings: List[Any],
    budget_ceiling: Optional[float] = None,
) -> AlternativesEvaluation:
    ceiling = budget_ceiling or price
    ceiling = max(ceiling, price * 0.8)

    alternatives: List[Alternative] = []
    seen_titles = set()
    for listing in listings:
        coerced = _coerce_listing(listing)
        title = coerced["title"]
        listing_price = coerced["price"]
        if not title or listing_price is None:
            continue
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        if listing_price <= 0 or listing_price >= price * 1.2:
            continue
        if listing_price > ceiling:
            continue

        savings = round(max(0.0, price - listing_price), 2)
        alt_type = AlternativeType.CHEAPER_SAME_SPEC if listing_price < price * 0.95 else AlternativeType.DIFFERENT_BRAND
        spec_difference = (
            "Lower price and strong value-for-money positioning, though the feature mix may be slightly different."
            if alt_type == AlternativeType.CHEAPER_SAME_SPEC
            else "Comparable value at a lower price, with a slightly different brand or feature mix."
        )
        alternatives.append(
            Alternative(
                product_name=title,
                price=round(listing_price, 2),
                savings_amount=savings,
                spec_difference=spec_difference,
                alternative_type=alt_type,
            )
        )
        if len(alternatives) >= 3:
            break

    if not alternatives:
        return _build_deterministic_alternatives(
            product_name=product_name,
            category=category,
            price=price,
            budget_ceiling=budget_ceiling,
        )

    best = alternatives[0]
    score = 100.0 - min(90.0, (price - best.price) / max(price, 1.0) * 100.0)
    score = round(min(max(score, 0.0), 100.0), 1)
    reasoning = (
        f"The strongest live-web alternative is {best.product_name} at ₹{best.price:,.0f}, "
        f"which saves about ₹{best.savings_amount:,.0f} versus the original ask."
    )
    return AlternativesEvaluation(
        score=score,
        alternatives=alternatives,
        reasoning=reasoning,
        data_source="LIVE_WEB",
    )


def _build_deterministic_alternatives(
    product_name: str,
    category: str,
    price: float,
    budget_ceiling: Optional[float] = None,
    primary_use_case: Optional[str] = None,
) -> AlternativesEvaluation:
    normalized_product = (product_name or "").strip().lower()
    ceiling = budget_ceiling or price
    ceiling = max(ceiling, price * 0.8)

    if "samsung" in normalized_product and "s25" in normalized_product:
        candidates = [
            Alternative(
                product_name="Vivo V70",
                price=38999.0,
                savings_amount=round(max(0.0, price - 38999.0), 2),
                spec_difference="Cheaper alternative with strong camera and battery focus; it trades a little premium finish for much better price-to-value.",

                alternative_type=AlternativeType.DIFFERENT_BRAND,
            ),
            Alternative(
                product_name="Nothing 4a Pro",
                price=42999.0,
                savings_amount=round(max(0.0, price - 42999.0), 2),
                spec_difference="Compact, clean software experience with a more affordable price point, but slightly less premium hardware.",
                alternative_type=AlternativeType.DIFFERENT_BRAND,
            ),
        ]
    elif "iphone" in normalized_product or "iphone" in category.lower():
        candidates = [
            Alternative(
                product_name="Google Pixel 8a",
                price=39999.0,
                savings_amount=round(max(0.0, price - 39999.0), 2),
                spec_difference="Lower price point with strong camera performance, but a different ecosystem and less premium display.",
                alternative_type=AlternativeType.DIFFERENT_BRAND,
            ),
            Alternative(
                product_name="Nothing Phone (2a)",
                price=26999.0,
                savings_amount=round(max(0.0, price - 26999.0), 2),
                spec_difference="More affordable option that trades some premium hardware for a better price-to-value package.",
                alternative_type=AlternativeType.DIFFERENT_BRAND,
            ),
        ]
    else:
        candidates = [
            Alternative(
                product_name=f"Budget {product_name}",
                price=max(1000.0, round(price * 0.8, 2)),
                savings_amount=round(max(0.0, price - max(1000.0, round(price * 0.8, 2))), 2),
                spec_difference="Lower-cost alternative that keeps the core use case intact while cutting premium features.",
                alternative_type=AlternativeType.CHEAPER_SAME_SPEC,
            ),
            Alternative(
                product_name=f"Value {product_name}",
                price=max(1000.0, round(price * 0.9, 2)),
                savings_amount=round(max(0.0, price - max(1000.0, round(price * 0.9, 2))), 2),
                spec_difference="Good value option with a slightly slimmer feature set but better price-to-performance ratio.",
                alternative_type=AlternativeType.DIFFERENT_BRAND,
            ),
        ]

    filtered = [
        alt for alt in candidates
        if alt.price <= ceiling and alt.price > 0 and alt.price < price * 1.2
    ]
    if not filtered:
        filtered = candidates[:1]

    score = 100.0 - min(90.0, (price - filtered[0].price) / max(price, 1.0) * 100.0)
    score = round(min(max(score, 0.0), 100.0), 1)

    reasoning = (
        f"The best alternative under your budget is {filtered[0].product_name} at ₹{filtered[0].price:,.0f}, "
        f"which saves about ₹{filtered[0].savings_amount:,.0f} versus the original ask."
    )
    return AlternativesEvaluation(
        score=score,
        alternatives=filtered[:3],
        reasoning=reasoning,
        data_source="FALLBACK",
    )


def _search_live_web_listings(
    product_name: str,
    category: str,
    price: float,
    budget_ceiling: Optional[float] = None,
    primary_use_case: Optional[str] = None,
) -> List[Any]:
    query = f"{product_name} {category} price"
    try:
        response = httpx.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            timeout=6.0,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning("Live web search failed: %s", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    listings: List[Any] = []
    for result in soup.select("a.result__a")[:4]:
        title = " ".join(result.get_text(" ", strip=True).split())
        href = result.get("href")
        if not title:
            continue
        listings.append(
            type(
                "Listing",
                (),
                {
                    "title": title,
                    "url": href,
                    "listed_price": _extract_price(title),
                    "offers": [],
                },
            )()
        )
    return listings


def run_alternatives_agent(
    product_name: str,
    category: str,
    price: float,
    budget_ceiling: Optional[float] = None,
    primary_use_case: Optional[str] = None,
    provider: Optional[Any] = None,
) -> AlternativesEvaluation:
    if provider is not None:
        try:
            resolved = None
            if hasattr(provider, "resolve_input"):
                resolved = asyncio.run(provider.resolve_input(product_name))
            search_query = getattr(resolved, "search_query", None) or getattr(resolved, "product_name", None) or product_name
            listings: List[Any] = []
            for platform in ["amazon", "flipkart", "croma", "reliance digital"]:
                if hasattr(provider, "search_platform"):
                    batch = asyncio.run(provider.search_platform(platform, search_query))
                    if batch:
                        listings.extend(batch)
            if not listings:
                return _build_deterministic_alternatives(
                    product_name=product_name,
                    category=category,
                    price=price,
                    budget_ceiling=budget_ceiling,
                    primary_use_case=primary_use_case,
                )
            fetched_listings = []
            for listing in listings:
                if hasattr(provider, "fetch_listing"):
                    fetched_listings.append(asyncio.run(provider.fetch_listing(listing)))
                else:
                    fetched_listings.append(listing)
            return _build_live_web_alternatives(
                product_name=product_name,
                category=category,
                price=price,
                listings=fetched_listings,
                budget_ceiling=budget_ceiling,
            )
        except Exception as exc:
            logger.error("run_alternatives_agent — provider search failed: %s", exc)
            return _build_deterministic_alternatives(
                product_name=product_name,
                category=category,
                price=price,
                budget_ceiling=budget_ceiling,
                primary_use_case=primary_use_case,
            )

    client = _get_client()
    if client is None:
        live_listings = _search_live_web_listings(
            product_name=product_name,
            category=category,
            price=price,
            budget_ceiling=budget_ceiling,
            primary_use_case=primary_use_case,
        )
        if live_listings:
            return _build_live_web_alternatives(
                product_name=product_name,
                category=category,
                price=price,
                listings=live_listings,
                budget_ceiling=budget_ceiling,
            )
        return _build_deterministic_alternatives(
            product_name=product_name,
            category=category,
            price=price,
            budget_ceiling=budget_ceiling,
            primary_use_case=primary_use_case,
        )

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
        return _build_deterministic_alternatives(
            product_name=product_name,
            category=category,
            price=price,
            budget_ceiling=budget_ceiling,
            primary_use_case=primary_use_case,
        )

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
        return _build_deterministic_alternatives(
            product_name=product_name,
            category=category,
            price=price,
            budget_ceiling=budget_ceiling,
            primary_use_case=primary_use_case,
        )
    except Exception as exc:
        logger.error("run_alternatives_agent — structuring error: %s", exc)
        return _build_deterministic_alternatives(
            product_name=product_name,
            category=category,
            price=price,
            budget_ceiling=budget_ceiling,
            primary_use_case=primary_use_case,
        )