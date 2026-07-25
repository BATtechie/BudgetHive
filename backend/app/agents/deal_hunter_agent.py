from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean, median, pstdev
from typing import Iterable, Sequence
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from app.schemas.deal_hunter import DealHunterResult, OfferDetail

logger = logging.getLogger(__name__)

SUPPORTED_PLATFORMS: tuple[str, ...] = (
    "Amazon.in",
    "Flipkart",
    "Croma",
    "Reliance Digital",
)

_DEFAULT_TIMEOUT = httpx.Timeout(12.0, connect=6.0)
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9,en-US;q=0.8",
}

_GENERIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

_DESCRIPTOR_STOPWORDS = {
    "bluetooth",
    "wired",
    "wireless",
    "headphone",
    "headphones",
    "earphone",
    "earphones",
    "earbud",
    "earbuds",
    "smartphone",
    "mobile",
    "phone",
    "phones",
    "laptop",
    "laptops",
    "tablet",
    "tablets",
    "watch",
    "smartwatch",
    "camera",
    "tv",
    "television",
}

_OFFERS_KEYWORDS = (
    "bank offer",
    "card offer",
    "cashback",
    "coupon",
    "discount",
    "offer",
    "save",
    "emi",
)

_PLATFORM_DOMAINS = {
    "amazon.in": "Amazon.in",
    "www.amazon.in": "Amazon.in",
    "flipkart.com": "Flipkart",
    "www.flipkart.com": "Flipkart",
    "croma.com": "Croma",
    "www.croma.com": "Croma",
    "reliancedigital.in": "Reliance Digital",
    "www.reliancedigital.in": "Reliance Digital",
}

_PLATFORM_SEARCH_URLS = {
    "Amazon.in": [lambda query: f"https://www.amazon.in/s?k={quote_plus(query)}"],
    "Flipkart": [lambda query: f"https://www.flipkart.com/search?q={quote_plus(query)}"],
    "Croma": [
        lambda query: f"https://www.croma.com/search/?text={quote_plus(query)}",
        lambda query: f"https://www.croma.com/searchB?q={quote_plus(query)}",
    ],
    "Reliance Digital": [
        lambda query: f"https://www.reliancedigital.in/search?q={quote_plus(query)}",
        lambda query: f"https://www.reliancedigital.in/search?text={quote_plus(query)}",
    ],
}


@dataclass
class ResolvedProductInput:
    raw_input: str
    input_type: str
    product_name: str
    search_query: str
    product_identifier: str
    source_platform: str | None = None
    source_url: str | None = None
    seed_listing: "ScrapedListing | None" = None


@dataclass
class ScrapedListing:
    platform: str
    title: str
    url: str
    listed_price: float | None = None
    source_page: str | None = None
    card_text: str | None = None
    exact_match: bool = False
    offers: list[OfferDetail] = field(default_factory=list)
    product_identifier: str = ""


@dataclass
class PriceHistorySummary:
    sample_count: int = 0
    average_price: float | None = None
    lowest_price: float | None = None
    stddev_price: float | None = None


@dataclass
class PriceHistoryEntry:
    checked_at: datetime
    price: float


PRICE_HISTORY_CACHE: defaultdict[str, list[PriceHistoryEntry]] = defaultdict(list)
_HISTORY_WINDOW = timedelta(days=90)


class PriceSourceProvider(ABC):
    @abstractmethod
    async def resolve_input(self, product_name_or_url: str) -> ResolvedProductInput:
        raise NotImplementedError

    @abstractmethod
    async def search_platform(self, platform: str, query: str) -> list[ScrapedListing]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_listing(self, listing: ScrapedListing) -> ScrapedListing:
        raise NotImplementedError


class WebPriceSourceProvider(PriceSourceProvider):
    def __init__(self, client: httpx.AsyncClient, timeout: httpx.Timeout | None = None):
        self._client = client
        self._timeout = timeout or _DEFAULT_TIMEOUT

    async def resolve_input(self, product_name_or_url: str) -> ResolvedProductInput:
        raw_input = product_name_or_url.strip()
        if _looks_like_url(raw_input):
            platform = _platform_from_url(raw_input)
            html = await self._safe_fetch_text(raw_input)
            title, price, offers = _parse_product_page(html or "", raw_input, platform)
            product_name = title or _slug_to_title(urlparse(raw_input).path) or raw_input
            product_identifier = _canonical_product_key(product_name)
            seed_listing = None
            if title or price is not None or offers:
                seed_listing = ScrapedListing(
                    platform=platform or _platform_from_url(raw_input) or "Unknown",
                    title=product_name,
                    url=raw_input,
                    listed_price=price,
                    source_page=raw_input,
                    exact_match=True,
                    offers=offers,
                    product_identifier=product_identifier,
                )
            return ResolvedProductInput(
                raw_input=raw_input,
                input_type="URL",
                product_name=product_name,
                search_query=product_name,
                product_identifier=product_identifier,
                source_platform=platform,
                source_url=raw_input,
                seed_listing=seed_listing,
            )

        product_name = raw_input
        return ResolvedProductInput(
            raw_input=raw_input,
            input_type="PRODUCT_NAME",
            product_name=product_name,
            search_query=product_name,
            product_identifier=_canonical_product_key(product_name),
        )

    async def search_platform(self, platform: str, query: str) -> list[ScrapedListing]:
        listings: list[ScrapedListing] = []
        for build_url in _PLATFORM_SEARCH_URLS.get(platform, []):
            search_url = build_url(query)
            html = await self._safe_fetch_text(search_url)
            if not html:
                continue
            listings.extend(_parse_search_results(html, search_url, platform))
            if listings:
                break
        return _dedupe_listings(listings)

    async def fetch_listing(self, listing: ScrapedListing) -> ScrapedListing:
        html = await self._safe_fetch_text(listing.url)
        if not html:
            return listing

        title, price, offers = _parse_product_page(html, listing.url, listing.platform)
        merged_offers = listing.offers[:]
        merged_offers.extend(offers)
        return ScrapedListing(
            platform=listing.platform,
            title=title or listing.title,
            url=listing.url,
            listed_price=price if price is not None else listing.listed_price,
            source_page=listing.source_page or listing.url,
            card_text=listing.card_text,
            exact_match=listing.exact_match,
            offers=_dedupe_offers(merged_offers),
            product_identifier=listing.product_identifier or _canonical_product_key(title or listing.title),
        )

    async def _safe_fetch_text(self, url: str) -> str | None:
        try:
            response = await self._client.get(
                url,
                headers=_DEFAULT_HEADERS,
                timeout=self._timeout,
                follow_redirects=True,
            )
            if response.status_code >= 400:
                logger.debug("Fetch failed for %s with status %s", url, response.status_code)
                return None
            return response.text
        except Exception as exc:  # pragma: no cover - network failures are handled gracefully
            logger.debug("Fetch failed for %s: %s", url, exc)
            return None


async def find_best_deal(
    product_name_or_url: str,
    *,
    db: object | None = None,
    provider: PriceSourceProvider | None = None,
    user_banks: Sequence[str] | None = None,
    monthly_savings_target: float | None = None,
    disposable_budget: float | None = None,
) -> DealHunterResult:
    """
    Find the best exact-match deal for a product or supported product URL.

    The result is intentionally honest: if live scraping fails or the exact match
    cannot be verified, the score drops and the reasoning says so.
    """
    owned_client: httpx.AsyncClient | None = None
    resolved: ResolvedProductInput | None = None
    provider_obj = provider
    priced_listings: list[ScrapedListing] = []
    now = datetime.now(timezone.utc)

    try:
        if provider_obj is None:
            owned_client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, headers=_DEFAULT_HEADERS, follow_redirects=True)
            provider_obj = WebPriceSourceProvider(owned_client)

        resolved = await provider_obj.resolve_input(product_name_or_url)

        candidates_by_platform: dict[str, ScrapedListing] = {}

        if resolved.seed_listing is not None:
            candidates_by_platform[resolved.seed_listing.platform] = resolved.seed_listing

        search_tasks = {
            platform: asyncio.create_task(provider_obj.search_platform(platform, resolved.search_query))
            for platform in SUPPORTED_PLATFORMS
        }
        search_results = await asyncio.gather(*search_tasks.values(), return_exceptions=True)

        for platform, result in zip(search_tasks.keys(), search_results, strict=True):
            if isinstance(result, Exception):
                logger.debug("Search failed for %s: %s", platform, result)
                continue

            exact_matches = [
                listing
                for listing in result
                if _is_exact_match(resolved.search_query, listing.title, resolved.product_identifier)
            ]
            if not exact_matches:
                continue

            best_match = _select_best_match(exact_matches, resolved.search_query)
            if platform not in candidates_by_platform:
                candidates_by_platform[platform] = best_match
            elif _match_strength(best_match.title, resolved.search_query) > _match_strength(
                candidates_by_platform[platform].title, resolved.search_query
            ):
                candidates_by_platform[platform] = best_match

        if not candidates_by_platform:
            return _empty_result(
                product_name=resolved.product_name,
                reason=(
                    "I could not verify an exact live match on the supported sites, so I am not fabricating "
                    "a price or deal score."
                ),
                now=now,
            )

        detail_tasks = {
            platform: asyncio.create_task(provider_obj.fetch_listing(listing))
            for platform, listing in candidates_by_platform.items()
        }
        detail_results = await asyncio.gather(*detail_tasks.values(), return_exceptions=True)

        final_listings: list[ScrapedListing] = []
        source_errors: list[str] = []
        for platform, result in zip(detail_tasks.keys(), detail_results, strict=True):
            if isinstance(result, Exception):
                logger.debug("Detail fetch failed for %s: %s", platform, result)
                source_errors.append(platform)
                final_listings.append(candidates_by_platform[platform])
                continue

            if result.listed_price is None:
                logger.debug("No price extracted for %s", platform)
            final_listings.append(
                ScrapedListing(
                    platform=result.platform,
                    title=result.title,
                    url=result.url,
                    listed_price=result.listed_price,
                    source_page=result.source_page,
                    card_text=result.card_text,
                    exact_match=result.exact_match,
                    offers=result.offers,
                    product_identifier=result.product_identifier or resolved.product_identifier,
                )
            )

        final_listings = _dedupe_listings(final_listings)
        priced_listings = [listing for listing in final_listings if listing.listed_price is not None and listing.listed_price > 0]

        if not priced_listings:
            return _empty_result(
                product_name=resolved.product_name,
                reason=(
                    "Exact matches were found, but no current price could be extracted from the live pages. "
                    "I’m returning a low-confidence result rather than inventing a number."
                ),
                now=now,
                matched_platforms=[listing.platform for listing in final_listings],
            )

        history = _load_history_summary(resolved.product_identifier, now)

        priced_records = [
            {
                "listing": listing,
                "effective_price": _effective_price(listing, user_banks=user_banks),
            }
            for listing in priced_listings
        ]
        priced_records.sort(key=lambda item: (item["effective_price"], item["listing"].listed_price or float("inf")))
        best_record = priced_records[0]
        best_listing = best_record["listing"]
        best_effective_price = float(best_record["effective_price"])
        best_offers = best_listing.offers

        matched_platforms = [record["listing"].platform for record in priced_records]

        historical_avg = history.average_price
        price_delta_pct = None
        historical_low = history.lowest_price
        if historical_avg and historical_avg > 0:
            price_delta_pct = round((float(best_listing.listed_price) - historical_avg) / historical_avg * 100.0, 2)

        deal_quality_score = _compute_deal_quality_score(
            best_listing=best_listing,
            all_listings=priced_records,
            history=history,
            best_effective_price=best_effective_price,
        )
        confidence = _determine_confidence(
            priced_count=len(priced_records),
            history=history,
            source_errors=source_errors,
            exact_match_count=len(final_listings),
        )

        reasoning = _build_reasoning(
            product_name=resolved.product_name,
            best_listing=best_listing,
            best_effective_price=best_effective_price,
            best_offers=best_offers,
            matched_platforms=matched_platforms,
            history=history,
            source_errors=source_errors,
            confidence=confidence,
        )
        savings_note = _build_savings_note(
            net_price=best_effective_price,
            monthly_savings_target=monthly_savings_target,
            disposable_budget=disposable_budget,
        )

        return DealHunterResult(
            product_name=resolved.product_name,
            matched_platforms=matched_platforms,
            best_price=round(float(best_listing.listed_price), 2),
            best_platform=best_listing.platform,
            historical_avg_90d=round(historical_avg, 2) if historical_avg is not None else None,
            price_delta_pct=price_delta_pct,
            offers=best_offers,
            deal_quality_score=round(deal_quality_score, 1),
            reasoning=reasoning,
            savings_impact_note=savings_note,
            data_confidence=confidence,
            last_checked_at=now,
        )

    except Exception as exc:  # pragma: no cover - final safety net
        logger.exception("Deal Hunter failed: %s", exc)
        now = datetime.now(timezone.utc)
        fallback_name = resolved.product_name if resolved is not None else product_name_or_url.strip()
        return _empty_result(
            product_name=fallback_name,
            reason=(
                "I hit an unexpected scraping error while checking live prices, so I returned a conservative "
                "low-confidence result instead of guessing."
            ),
            now=now,
        )
    finally:
        if resolved is not None and priced_listings:
            _record_price_history(resolved.product_identifier, priced_listings, now)
        if owned_client is not None:
            await owned_client.aclose()


def run_deal_hunter_agent(
    product_query: str,
    *,
    db: object | None = None,
    provider: PriceSourceProvider | None = None,
    user_banks: Sequence[str] | None = None,
    monthly_savings_target: float | None = None,
    disposable_budget: float | None = None,
) -> DealHunterResult:
    """Synchronous wrapper for scripts and legacy call sites."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            find_best_deal(
                product_query,
                db=db,
                provider=provider,
                user_banks=user_banks,
                monthly_savings_target=monthly_savings_target,
                disposable_budget=disposable_budget,
            )
        )

    raise RuntimeError("run_deal_hunter_agent() cannot be called from an active event loop; await find_best_deal().")


def _empty_result(
    *,
    product_name: str,
    reason: str,
    now: datetime,
    matched_platforms: list[str] | None = None,
) -> DealHunterResult:
    return DealHunterResult(
        product_name=product_name,
        matched_platforms=matched_platforms or [],
        best_price=None,
        best_platform="Unavailable",
        historical_avg_90d=None,
        price_delta_pct=None,
        offers=[],
        deal_quality_score=0.0,
        reasoning=reason,
        savings_impact_note=None,
        data_confidence="low",
        last_checked_at=now,
    )


def _record_price_history(
    product_identifier: str,
    listings: Sequence[ScrapedListing],
    checked_at: datetime,
) -> None:
    history = PRICE_HISTORY_CACHE[product_identifier]
    for listing in listings:
        if listing.listed_price is None or listing.listed_price <= 0:
            continue
        history.append(PriceHistoryEntry(checked_at=checked_at, price=float(listing.listed_price)))
    cutoff = checked_at - _HISTORY_WINDOW
    PRICE_HISTORY_CACHE[product_identifier] = [
        entry for entry in history if entry.checked_at >= cutoff and entry.price > 0
    ]


def _load_history_summary(product_identifier: str, now: datetime | None = None) -> PriceHistorySummary:
    history = PRICE_HISTORY_CACHE.get(product_identifier, [])
    if not history:
        return PriceHistorySummary()

    cutoff = (now or datetime.now(timezone.utc)) - _HISTORY_WINDOW
    recent_prices = [entry.price for entry in history if entry.checked_at >= cutoff and entry.price > 0]
    PRICE_HISTORY_CACHE[product_identifier] = [
        entry for entry in history if entry.checked_at >= cutoff and entry.price > 0
    ]
    if not recent_prices:
        return PriceHistorySummary()

    prices = recent_prices
    if not prices:
        return PriceHistorySummary()

    average_price = mean(prices)
    lowest_price = min(prices)
    stddev_price = pstdev(prices) if len(prices) > 1 else 0.0
    return PriceHistorySummary(
        sample_count=len(prices),
        average_price=average_price,
        lowest_price=lowest_price,
        stddev_price=stddev_price,
    )


def _compute_deal_quality_score(
    *,
    best_listing: ScrapedListing,
    all_listings: Sequence[dict[str, object]],
    history: PriceHistorySummary,
    best_effective_price: float,
) -> float:
    listed_price = float(best_listing.listed_price) if best_listing.listed_price is not None else 0.0
    price_component = 35.0
    if history.sample_count and history.average_price and history.average_price > 0:
        average_price = history.average_price
        relative_delta = (average_price - listed_price) / average_price
        price_component = 45.0 + (relative_delta * 45.0)
        if history.lowest_price and listed_price <= history.lowest_price * 1.03:
            price_component += 10.0
    elif len(all_listings) > 1:
        competitor_prices = [
            float(item["listing"].listed_price)
            for item in all_listings
            if item["listing"].listed_price is not None
        ]
        if len(competitor_prices) >= 2:
            median_price = median(competitor_prices)
            relative_delta = (median_price - listed_price) / median_price if median_price else 0.0
            price_component = 42.0 + (relative_delta * 35.0)
        else:
            price_component = 38.0

    offer_component = 0.0
    for offer in best_listing.offers:
        if offer.offer_type in {"bank_discount", "instant_discount"}:
            offer_component += 8.0
        elif offer.offer_type == "coupon":
            offer_component += 6.0
        elif offer.offer_type == "cashback":
            offer_component += 4.0
        else:
            offer_component += 2.0
    offer_component = min(25.0, offer_component)

    volatility_component = 6.0
    if history.sample_count >= 2 and history.stddev_price is not None and history.average_price:
        coeff_variation = history.stddev_price / history.average_price if history.average_price else 0.0
        volatility_component = max(0.0, 15.0 - (coeff_variation * 100.0))
    elif history.sample_count == 1:
        volatility_component = 8.0

    source_component = min(10.0, max(0.0, (len(all_listings) - 1) * 3.0))

    effective_bonus = 0.0
    if best_effective_price and listed_price:
        discount_ratio = max(0.0, (listed_price - best_effective_price) / listed_price)
        effective_bonus = min(12.0, discount_ratio * 60.0)

    score = price_component + offer_component + volatility_component + source_component + effective_bonus
    return max(0.0, min(100.0, score))


def _determine_confidence(
    *,
    priced_count: int,
    history: PriceHistorySummary,
    source_errors: Sequence[str],
    exact_match_count: int,
) -> str:
    if priced_count >= 3 and history.sample_count >= 3:
        return "high"
    if priced_count >= 2 or history.sample_count >= 3:
        return "medium"
    if priced_count >= 1 and exact_match_count >= 1 and not source_errors:
        return "medium"
    return "low"


def _build_reasoning(
    *,
    product_name: str,
    best_listing: ScrapedListing,
    best_effective_price: float,
    best_offers: Sequence[OfferDetail],
    matched_platforms: Sequence[str],
    history: PriceHistorySummary,
    source_errors: Sequence[str],
    confidence: str,
) -> str:
    parts: list[str] = []
    parts.append(
        f"Current best: ₹{best_listing.listed_price:,.0f} on {best_listing.platform}."
    )
    if history.sample_count and history.average_price is not None:
        delta_pct = (float(best_listing.listed_price) - history.average_price) / history.average_price * 100.0
        parts.append(
            f"It is {abs(delta_pct):.1f}% {'below' if delta_pct < 0 else 'above'} the 90-day average of ₹{history.average_price:,.0f}."
        )
        if history.lowest_price is not None:
            if best_listing.listed_price is not None and best_listing.listed_price <= history.lowest_price * 1.03:
                parts.append(f"It is also close to the 90-day low of ₹{history.lowest_price:,.0f}.")
    else:
        parts.append(
            "I do not yet have enough in-memory 90-day price history to calculate a reliable trend, so I am not fabricating one."
        )

    if best_offers:
        offer_bits = []
        for offer in best_offers[:3]:
            amount = None
            if offer.discount_value is not None:
                if offer.discount_unit == "PERCENT":
                    amount = f"{offer.discount_value:.0f}%"
                else:
                    amount = f"₹{offer.discount_value:,.0f}"
            if offer.issuer and amount:
                offer_bits.append(f"{offer.issuer} gives {amount} off")
            elif offer.issuer:
                offer_bits.append(f"{offer.issuer} offer is active")
            elif amount:
                offer_bits.append(f"An active offer saves about {amount}")
        if offer_bits:
            parts.append(" ".join(offer_bits) + ".")
    else:
        parts.append("No active bank, coupon, or cashback offer was clearly visible on the best platform page.")

    if len(matched_platforms) > 1:
        others = ", ".join(sorted(set(matched_platforms)))
        parts.append(f"I matched the same exact product across {len(set(matched_platforms))} platforms: {others}.")

    if source_errors:
        parts.append(
            f"Some pages were slower or blocked during live fetches ({', '.join(sorted(set(source_errors)))}), so confidence is {confidence}."
        )
    else:
        parts.append(f"Live source coverage is {confidence}.")

    if history.sample_count and history.average_price is not None and best_listing.listed_price is not None:
        trend = float(best_listing.listed_price) - history.average_price
        if trend < 0:
            parts.append("Waiting is unlikely to save much unless a new sale appears.")
        else:
            parts.append("If you are not in a hurry, waiting could still improve the price.")
    else:
        parts.append("Because live history is still thin, treat this as a live-market snapshot rather than a long-term trend call.")

    return " ".join(parts)


def _build_savings_note(
    *,
    net_price: float,
    monthly_savings_target: float | None,
    disposable_budget: float | None,
) -> str | None:
    targets = []
    if monthly_savings_target is not None and monthly_savings_target > 0:
        targets.append(("monthly savings target", monthly_savings_target))
    if disposable_budget is not None and disposable_budget > 0:
        targets.append(("disposable budget", disposable_budget))
    if not targets:
        return None

    label, value = targets[0]
    pct = (net_price / value) * 100.0
    remaining = value - net_price
    if remaining >= 0:
        return (
            f"After live offers, this is about ₹{net_price:,.0f}, or {pct:.1f}% of your {label} of ₹{value:,.0f}. "
            f"That leaves roughly ₹{remaining:,.0f} of room."
        )
    return (
        f"After live offers, this is about ₹{net_price:,.0f}, which is {abs(remaining):,.0f} above your {label} of ₹{value:,.0f}."
    )


def _effective_price(listing: ScrapedListing, user_banks: Sequence[str] | None = None) -> float:
    if listing.listed_price is None:
        return 0.0

    discounts = 0.0
    for offer in listing.offers:
        if offer.offer_type not in {"bank_discount", "instant_discount", "coupon"}:
            continue
        if offer.offer_type == "bank_discount" and user_banks and not _offer_matches_user_banks(offer, user_banks):
            continue
        if offer.discount_value is not None and offer.discount_value > 0:
            discounts += offer.discount_value
    return max(0.0, float(listing.listed_price) - discounts)


def _offer_matches_user_banks(offer: OfferDetail, user_banks: Sequence[str]) -> bool:
    issuer = _normalize_text(offer.issuer or "")
    conditions = _normalize_text(offer.conditions or "")
    offer_text = f"{issuer} {conditions}".strip()
    if not offer_text:
        return False

    for bank in user_banks:
        bank_text = _normalize_text(bank)
        if not bank_text:
            continue
        if bank_text in offer_text or offer_text in bank_text:
            return True
    return False


def _parse_search_results(html: str, page_url: str, platform: str) -> list[ScrapedListing]:
    soup = BeautifulSoup(html, "html.parser")
    if platform == "Amazon.in":
        listings = _parse_amazon_search_results(soup, page_url)
    else:
        listings = _parse_generic_search_results(soup, page_url, platform)
    return _dedupe_listings(listings)


def _parse_amazon_search_results(soup: BeautifulSoup, page_url: str) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    for card in soup.select("div[data-component-type='s-search-result']"):
        title_node = card.select_one("h2 a span") or card.select_one("h2 span")
        link_node = card.select_one("h2 a")
        if not title_node or not link_node:
            continue
        title = _clean_text(title_node.get_text(" ", strip=True))
        url = urljoin(page_url, link_node.get("href", ""))
        price = _extract_price_from_container(card)
        listings.append(
            ScrapedListing(
                platform="Amazon.in",
                title=title,
                url=url,
                listed_price=price,
                source_page=page_url,
                card_text=_clean_text(card.get_text(" ", strip=True)),
                product_identifier=_canonical_product_key(title),
            )
        )
    if listings:
        return listings
    return _parse_generic_search_results(soup, page_url, "Amazon.in")


def _parse_generic_search_results(soup: BeautifulSoup, page_url: str, platform: str) -> list[ScrapedListing]:
    listings: list[ScrapedListing] = []
    seen: set[tuple[str, str]] = set()
    for container in soup.find_all(["article", "div", "li", "section"]):
        text = _clean_text(container.get_text(" ", strip=True))
        if not text or len(text) < 15:
            continue
        if not _contains_price(text):
            continue

        title = _extract_title_from_container(container)
        url = _extract_url_from_container(container, page_url)
        if not title or not url:
            continue
        key = (_normalize_text(title), url)
        if key in seen:
            continue
        seen.add(key)
        listings.append(
            ScrapedListing(
                platform=platform,
                title=title,
                url=url,
                listed_price=_extract_price_from_container(container),
                source_page=page_url,
                card_text=text,
                product_identifier=_canonical_product_key(title),
            )
        )
    return listings


def _parse_product_page(html: str, page_url: str, platform: str | None) -> tuple[str | None, float | None, list[OfferDetail]]:
    if not html:
        return None, None, []
    soup = BeautifulSoup(html, "html.parser")
    title = _extract_page_title(soup)
    price = _extract_price_from_page(soup)
    offers = _extract_offers_from_page(soup, platform or _platform_from_url(page_url), price)
    if title:
        title = _clean_text(title)
    return title, price, offers


def _extract_page_title(soup: BeautifulSoup) -> str | None:
    selectors = [
        "meta[property='og:title']",
        "meta[name='twitter:title']",
        "meta[property='product:title']",
        "meta[itemprop='name']",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node and node.get("content"):
            return _clean_text(node.get("content", ""))

    product_title = soup.select_one("#productTitle") or soup.select_one("h1")
    if product_title:
        title = _clean_text(product_title.get_text(" ", strip=True))
        if title:
            return title

    if soup.title and soup.title.string:
        return _clean_text(soup.title.string)
    return None


def _extract_price_from_page(soup: BeautifulSoup) -> float | None:
    meta_selectors = [
        "meta[property='product:price:amount']",
        "meta[property='og:price:amount']",
        "meta[itemprop='price']",
        "meta[name='twitter:data1']",
    ]
    for selector in meta_selectors:
        node = soup.select_one(selector)
        if node:
            candidate = node.get("content") or node.get("value")
            price = _parse_price(candidate or "")
            if price is not None:
                return price

    jsonld_prices = _extract_jsonld_prices(soup)
    if jsonld_prices:
        return jsonld_prices[0]

    selector_groups = [
        "#priceblock_dealprice",
        "#priceblock_ourprice",
        "#price_inside_buybox",
        "#productPrice",
        "span.a-price span.a-offscreen",
        ".a-price .a-offscreen",
        ".Nx9bqj",
        ".pdp-price",
        ".product-price",
        ".price",
    ]
    for selector in selector_groups:
        for node in soup.select(selector):
            price = _parse_price(node.get_text(" ", strip=True) or node.get("content", ""))
            if price is not None:
                return price

    text_prices = _extract_price_candidates(soup.get_text("\n", strip=True))
    return text_prices[0] if text_prices else None


def _extract_jsonld_prices(soup: BeautifulSoup) -> list[float]:
    prices: list[float] = []
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        for value in _walk_json(payload):
            if isinstance(value, dict):
                for key in ("price", "priceValue", "lowPrice", "highPrice"):
                    if key in value:
                        price = _parse_price(str(value[key]))
                        if price is not None:
                            prices.append(price)
        if prices:
            break
    return prices


def _walk_json(value: object) -> Iterable[object]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_json(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _extract_offers_from_page(soup: BeautifulSoup, platform: str, current_price: float | None) -> list[OfferDetail]:
    lines = [
        _clean_text(line)
        for line in soup.get_text("\n", strip=True).splitlines()
        if _clean_text(line)
    ]
    offers: list[OfferDetail] = []
    seen: set[tuple[str, str | None, float | None, str | None]] = set()
    for index, line in enumerate(lines):
        lower = line.lower()
        if not any(keyword in lower for keyword in _OFFERS_KEYWORDS):
            continue
        window = " ".join(lines[index : min(index + 4, len(lines))])
        parsed_offers = _parse_offer_window(window, current_price)
        for offer in parsed_offers:
            key = (offer.offer_type, offer.issuer, offer.discount_value, offer.discount_unit)
            if key in seen:
                continue
            seen.add(key)
            offers.append(offer)
    return _dedupe_offers(offers)


def _parse_offer_window(window: str, current_price: float | None) -> list[OfferDetail]:
    offers: list[OfferDetail] = []
    lower = window.lower()

    issuer = _extract_issuer(window)
    cap_match = re.search(r"(?:up to|upto)\s*₹\s*([\d,]+(?:\.\d+)?)", window, re.IGNORECASE)
    amount_match = re.search(r"(?:flat|save|discount|off)\s*₹\s*([\d,]+(?:\.\d+)?)", window, re.IGNORECASE)
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", window)
    coupon_match = re.search(r"(?:coupon|code)\s*(?:code)?[:\s]*([A-Z0-9_-]{4,})", window, re.IGNORECASE)

    if "cashback" in lower:
        offer_type = "cashback"
        discount_value = None
        discount_unit = None
        if pct_match and current_price:
            discount_value = round(current_price * (float(pct_match.group(1)) / 100.0), 2)
            discount_unit = "INR"
        elif amount_match:
            discount_value = _parse_price(amount_match.group(1))
            discount_unit = "INR"
        elif cap_match:
            discount_value = _parse_price(cap_match.group(1))
            discount_unit = "INR"
        offers.append(
            OfferDetail(
                offer_type=offer_type,
                issuer=issuer or "Cashback",
                discount_value=discount_value,
                discount_unit=discount_unit,
                conditions=window,
            )
        )

    if coupon_match:
        code = coupon_match.group(1).strip()
        discount_value = None
        discount_unit = None
        if amount_match:
            discount_value = _parse_price(amount_match.group(1))
            discount_unit = "INR"
        elif pct_match and current_price:
            discount_value = round(current_price * (float(pct_match.group(1)) / 100.0), 2)
            discount_unit = "INR"
        elif cap_match:
            discount_value = _parse_price(cap_match.group(1))
            discount_unit = "INR"
        offers.append(
            OfferDetail(
                offer_type="coupon",
                issuer=code,
                discount_value=discount_value,
                discount_unit=discount_unit,
                conditions=window,
            )
        )

    if "bank" in lower or "card" in lower or "credit" in lower or "debit" in lower:
        discount_value = None
        discount_unit = None
        if pct_match and current_price:
            discount_value = round(current_price * (float(pct_match.group(1)) / 100.0), 2)
            discount_unit = "INR"
        elif amount_match:
            discount_value = _parse_price(amount_match.group(1))
            discount_unit = "INR"
        elif cap_match:
            discount_value = _parse_price(cap_match.group(1))
            discount_unit = "INR"
        offers.append(
            OfferDetail(
                offer_type="bank_discount",
                issuer=issuer or "Eligible card",
                discount_value=discount_value,
                discount_unit=discount_unit,
                conditions=window,
            )
        )

    if "discount" in lower and not any(
        offer.offer_type in {"bank_discount", "instant_discount"} for offer in offers
    ):
        discount_value = None
        discount_unit = None
        if pct_match and current_price:
            discount_value = round(current_price * (float(pct_match.group(1)) / 100.0), 2)
            discount_unit = "INR"
        elif amount_match:
            discount_value = _parse_price(amount_match.group(1))
            discount_unit = "INR"
        elif cap_match:
            discount_value = _parse_price(cap_match.group(1))
            discount_unit = "INR"
        offers.append(
            OfferDetail(
                offer_type="instant_discount",
                issuer=issuer,
                discount_value=discount_value,
                discount_unit=discount_unit,
                conditions=window,
            )
        )

    return offers


def _extract_issuer(window: str) -> str | None:
    patterns = [
        r"(Amazon Pay ICICI Bank Credit Card(?:s)?)",
        r"(Flipkart Axis Bank Credit Card(?:s)?)",
        r"(HDFC Bank(?: Credit Card| Debit Card| Cards| Card| Debit Cards)?)",
        r"(ICICI Bank(?: Credit Card| Debit Card| Cards| Card| Debit Cards)?)",
        r"(SBI Card(?:s)?)",
        r"(Axis Bank(?: Credit Card| Debit Card| Cards| Card| Debit Cards)?)",
        r"(Kotak(?: Bank)?(?: Credit Card| Debit Card| Cards| Card| Debit Cards)?)",
        r"(Amazon Pay(?: Balance)?)",
        r"(select Credit Cards?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, window, re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))

    with_match = re.search(r"\bwith\s+([^.;,\n]+)", window, re.IGNORECASE)
    if with_match:
        issuer = _clean_text(with_match.group(1))
        issuer = re.sub(r"\b(cards?|credit cards?|debit cards?)\b", "", issuer, flags=re.IGNORECASE).strip()
        if issuer:
            return issuer
    on_match = re.search(r"\bon\s+([^.;,\n]+)", window, re.IGNORECASE)
    if on_match:
        issuer = _clean_text(on_match.group(1))
        issuer = re.sub(r"\b(cards?|credit cards?|debit cards?)\b", "", issuer, flags=re.IGNORECASE).strip()
        if issuer:
            return issuer
    return None


def _extract_title_from_container(container: BeautifulSoup) -> str | None:
    title_nodes = container.find_all(["h1", "h2", "h3", "h4", "h5", "span", "a"], limit=12)
    for node in title_nodes:
        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if _contains_price(text):
            continue
        if len(text) < 4:
            continue
        if any(keyword in text.lower() for keyword in ("add to cart", "compare", "offer", "save", "buy")):
            continue
        return text
    return None


def _extract_url_from_container(container: BeautifulSoup, page_url: str) -> str | None:
    for node in container.find_all("a", href=True, limit=12):
        href = node.get("href", "")
        if not href:
            continue
        if href.startswith("#") or href.startswith("javascript:"):
            continue
        url = urljoin(page_url, href)
        if _is_product_url(url):
            return url
    return None


def _extract_price_from_container(container: BeautifulSoup) -> float | None:
    selectors = [
        ".a-price .a-offscreen",
        ".a-price-whole",
        "span._30jeq3",
        "span.Nx9bqj",
        ".product-price",
        ".price",
    ]
    for selector in selectors:
        node = container.select_one(selector)
        if node:
            price = _parse_price(node.get_text(" ", strip=True) or node.get("content", ""))
            if price is not None:
                return price
    text_prices = _extract_price_candidates(_clean_text(container.get_text(" ", strip=True)))
    return text_prices[0] if text_prices else None


def _extract_price_candidates(text: str) -> list[float]:
    prices: list[float] = []
    for match in re.finditer(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)", text, re.IGNORECASE):
        price = _parse_price(match.group(1))
        if price is not None:
            prices.append(price)
    if not prices:
        for match in re.finditer(r"\b([\d,]{3,}(?:\.\d+)?)\b", text):
            candidate = _parse_price(match.group(1))
            if candidate is not None:
                prices.append(candidate)
    return prices


def _parse_price(value: str) -> float | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(value))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _contains_price(text: str) -> bool:
    return bool(re.search(r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?", text, re.IGNORECASE))


def _clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalize_text(text: str) -> str:
    text = _clean_text(text)
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _significant_tokens(text: str) -> list[str]:
    tokens = []
    for token in _normalize_text(text).split():
        if token in _GENERIC_STOPWORDS or token in _DESCRIPTOR_STOPWORDS:
            continue
        if len(token) <= 1:
            continue
        tokens.append(token)
    return tokens


def _canonical_product_key(text: str) -> str:
    tokens = _significant_tokens(text)
    if not tokens:
        return _normalize_text(text)

    model_token = next((token for token in tokens if any(char.isdigit() for char in token)), None)
    if model_token is not None:
        prefix = tokens[:2] if len(tokens) >= 2 else tokens[:1]
        return "-".join(prefix + [model_token])

    return "-".join(tokens[:4])


def _match_strength(query: str, candidate: str) -> int:
    query_tokens = _significant_tokens(query)
    candidate_tokens = _significant_tokens(candidate)
    score = 0
    if _normalize_text(query) == _normalize_text(candidate):
        score += 100
    if _canonical_product_key(query) == _canonical_product_key(candidate):
        score += 80
    if query_tokens and set(query_tokens).issubset(set(candidate_tokens)):
        score += 50 + len(query_tokens)
    if any(token for token in query_tokens if token in candidate_tokens):
        score += 10
    return score


def _is_exact_match(query: str, candidate_title: str, query_identifier: str) -> bool:
    query_tokens = _significant_tokens(query)
    candidate_tokens = _significant_tokens(candidate_title)
    if not query_tokens or not candidate_tokens:
        return False

    if _canonical_product_key(candidate_title) == query_identifier:
        return True

    if set(query_tokens).issubset(set(candidate_tokens)):
        return True

    return _match_strength(query, candidate_title) >= 60


def _select_best_match(listings: Sequence[ScrapedListing], query: str) -> ScrapedListing:
    return sorted(
        listings,
        key=lambda listing: (
            -_match_strength(query, listing.title),
            listing.listed_price if listing.listed_price is not None else float("inf"),
        ),
    )[0]


def _dedupe_listings(listings: Sequence[ScrapedListing]) -> list[ScrapedListing]:
    deduped: dict[tuple[str, str], ScrapedListing] = {}
    for listing in listings:
        key = (_normalize_text(listing.title), listing.url)
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = listing
            continue
        if existing.listed_price is None and listing.listed_price is not None:
            deduped[key] = listing
        elif listing.listed_price is not None and existing.listed_price is not None and listing.listed_price < existing.listed_price:
            deduped[key] = listing
    return list(deduped.values())


def _dedupe_offers(offers: Sequence[OfferDetail]) -> list[OfferDetail]:
    deduped: dict[tuple[str, str | None, float | None, str | None], OfferDetail] = {}
    for offer in offers:
        key = (offer.offer_type, offer.issuer, offer.discount_value, offer.discount_unit)
        deduped.setdefault(key, offer)
    return list(deduped.values())


def _looks_like_url(text: str) -> bool:
    return bool(re.match(r"https?://", text.strip(), re.IGNORECASE))


def _platform_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    return _PLATFORM_DOMAINS.get(parsed.netloc.lower())


def _is_product_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(domain in parsed.netloc.lower() for domain in _PLATFORM_DOMAINS):
        return True
    return any(
        token in path
        for token in (
            "/dp/",
            "/gp/product",
            "/p/",
            "/product/",
            "/products/",
            "/item/",
        )
    )


def _slug_to_title(path: str) -> str | None:
    slug = path.strip("/").split("/")[-1]
    if not slug:
        return None
    slug = slug.split("?")[0].split("#")[0]
    if not slug:
        return None
    words = [word for word in re.split(r"[-_]+", slug) if word and not word.isdigit()]
    if not words:
        return None
    return _clean_text(" ".join(words)).title()
