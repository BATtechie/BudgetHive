from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.agents.deal_hunter_agent as deal_hunter_agent
from app.agents.deal_hunter_agent import PriceHistorySummary, WebPriceSourceProvider, find_best_deal


AMAZON_SEARCH_HTML = """
<html>
  <body>
    <div data-component-type="s-search-result">
      <h2><a href="/dp/B0XM4"><span>SONY WH-1000XM4 Wireless Headphones</span></a></h2>
      <span class="a-price"><span class="a-offscreen">₹22,990.00</span></span>
    </div>
    <div data-component-type="s-search-result">
      <h2><a href="/dp/B0XM5"><span>Sony WH-1000XM5 Wireless Headphones</span></a></h2>
      <span class="a-price"><span class="a-offscreen">₹29,990.00</span></span>
    </div>
  </body>
</html>
"""

AMAZON_PRODUCT_HTML = """
<html>
  <head>
    <meta property="og:title" content="Sony WH-1000XM5 Wireless Headphones" />
    <meta property="product:price:amount" content="29990.00" />
  </head>
  <body>
    <h1 id="productTitle">Sony WH-1000XM5 Wireless Headphones</h1>
    <div>Bank Offer Upto ₹3,000.00 discount on HDFC Bank Credit Cards</div>
    <div>Cashback Upto ₹149.00 cashback as Amazon Pay ICICI Bank Credit Cards</div>
  </body>
</html>
"""

FLIPKART_SEARCH_HTML = """
<html>
  <body>
    <div class="_1AtVbE">
      <a href="/sony-wh-1000xm5/p/itm123">
        <div>SONY WH-1000XM5 Designed with Adaptive ANC and 30 Hours of Battery life</div>
      </a>
      <div class="Nx9bqj">₹24,990</div>
    </div>
  </body>
</html>
"""

FLIPKART_PRODUCT_HTML = """
<html>
  <head>
    <meta property="og:title" content="SONY WH-1000XM5 Designed with Adaptive ANC and 30 Hours of Battery life" />
    <meta itemprop="price" content="24990" />
  </head>
  <body>
    <h1>SONY WH-1000XM5 Designed with Adaptive ANC and 30 Hours of Battery life</h1>
    <div>10% instant discount with HDFC Bank cards up to ₹500</div>
    <div>Save ₹250 with coupon SAVE250</div>
  </body>
</html>
"""

CROMA_SEARCH_HTML = """
<html>
  <body>
    <article>
      <a href="/p/sony-wh-1000xm5-headphones">SONY WH-1000XM5 Bluetooth Headphone with Mic</a>
      <div class="price">₹29,990</div>
    </article>
  </body>
</html>
"""

CROMA_PRODUCT_HTML = """
<html>
  <head>
    <meta property="og:title" content="SONY WH-1000XM5 Bluetooth Headphone with Mic" />
    <meta itemprop="price" content="29990" />
  </head>
  <body>
    <h1>SONY WH-1000XM5 Bluetooth Headphone with Mic</h1>
    <div>No active promo currently visible.</div>
  </body>
</html>
"""

RELIANCE_SEARCH_HTML = """
<html>
  <body>
    <div>
      <a href="/sony-wh-1000xm5/p/491234">
        Sony WH-1000XM5 Wireless Industry Leading Active Noise Cancelling Headphones
      </a>
      <div>₹31,990.00</div>
    </div>
  </body>
</html>
"""

RELIANCE_PRODUCT_HTML = """
<html>
  <head>
    <meta property="og:title" content="Sony WH-1000XM5 Wireless Industry Leading Active Noise Cancelling Headphones" />
    <meta itemprop="price" content="31990.00" />
  </head>
  <body>
    <h1>Sony WH-1000XM5 Wireless Industry Leading Active Noise Cancelling Headphones</h1>
  </body>
</html>
"""

AMAZON_NO_PRICE_SEARCH_HTML = """
<html>
  <body>
    <div data-component-type="s-search-result">
      <h2><a href="/dp/B0NOPRICE"><span>Sony WH-1000XM5 Wireless Headphones</span></a></h2>
    </div>
  </body>
</html>
"""

AMAZON_NO_PRICE_PRODUCT_HTML = """
<html>
  <head>
    <meta property="og:title" content="Sony WH-1000XM5 Wireless Headphones" />
  </head>
  <body>
    <h1 id="productTitle">Sony WH-1000XM5 Wireless Headphones</h1>
    <div>Price currently unavailable</div>
  </body>
</html>
"""


def _priced_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host or ""
    path = request.url.path or ""

    if host in {"amazon.in", "www.amazon.in"}:
        if path.startswith("/dp/B0XM5"):
            return httpx.Response(200, text=AMAZON_PRODUCT_HTML, request=request)
        if path.startswith("/dp/B0XM4"):
            return httpx.Response(
                200,
                text=AMAZON_PRODUCT_HTML.replace("WH-1000XM5", "WH-1000XM4").replace("29990.00", "22990.00"),
                request=request,
            )
        if path.startswith("/s"):
            return httpx.Response(200, text=AMAZON_SEARCH_HTML, request=request)

    if host in {"flipkart.com", "www.flipkart.com"}:
        if path.startswith("/sony-wh-1000xm5/p/itm123") or path.startswith("/p/itm123"):
            return httpx.Response(200, text=FLIPKART_PRODUCT_HTML, request=request)
        if path.startswith("/search"):
            return httpx.Response(200, text=FLIPKART_SEARCH_HTML, request=request)

    if host in {"croma.com", "www.croma.com"}:
        if path.startswith("/p/sony-wh-1000xm5-headphones"):
            return httpx.Response(200, text=CROMA_PRODUCT_HTML, request=request)
        if path.startswith("/search") or path.startswith("/searchB"):
            return httpx.Response(200, text=CROMA_SEARCH_HTML, request=request)

    if host in {"reliancedigital.in", "www.reliancedigital.in"}:
        if path.startswith("/sony-wh-1000xm5/p/491234"):
            return httpx.Response(200, text=RELIANCE_PRODUCT_HTML, request=request)
        if path.startswith("/search") or path.startswith("/collection"):
            return httpx.Response(200, text=RELIANCE_SEARCH_HTML, request=request)

    return httpx.Response(404, text="not found", request=request)


def _no_price_handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host or ""
    path = request.url.path or ""

    if host in {"amazon.in", "www.amazon.in"}:
        if path.startswith("/dp/B0NOPRICE"):
            return httpx.Response(200, text=AMAZON_NO_PRICE_PRODUCT_HTML, request=request)
        if path.startswith("/s"):
            return httpx.Response(200, text=AMAZON_NO_PRICE_SEARCH_HTML, request=request)

    return httpx.Response(404, text="not found", request=request)


class DealHunterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        deal_hunter_agent.PRICE_HISTORY_CACHE.clear()
        self.priced_client = httpx.AsyncClient(
            transport=httpx.MockTransport(_priced_handler),
            follow_redirects=True,
        )
        self.no_price_client = httpx.AsyncClient(
            transport=httpx.MockTransport(_no_price_handler),
            follow_redirects=True,
        )
        self.priced_provider = WebPriceSourceProvider(self.priced_client)
        self.no_price_provider = WebPriceSourceProvider(self.no_price_client)
        self.addAsyncCleanup(self.priced_client.aclose)
        self.addAsyncCleanup(self.no_price_client.aclose)

    async def test_exact_match_chooses_best_price_and_uses_history(self) -> None:
        history = PriceHistorySummary(
            sample_count=6,
            average_price=28500.0,
            lowest_price=24500.0,
            stddev_price=1200.0,
        )

        with patch("app.agents.deal_hunter_agent._load_history_summary", return_value=history):
            result = await find_best_deal(
                "Sony WH-1000XM5 Wireless Headphones",
                provider=self.priced_provider,
                monthly_savings_target=50000.0,
            )

        self.assertEqual(result.product_name, "Sony WH-1000XM5 Wireless Headphones")
        self.assertEqual(result.best_platform, "Flipkart")
        self.assertIsNotNone(result.best_price)
        self.assertAlmostEqual(result.best_price, 24990.0)
        self.assertIsNotNone(result.price_delta_pct)
        self.assertLess(result.price_delta_pct, 0)
        self.assertEqual(result.historical_avg_90d, 28500.0)
        self.assertEqual(result.data_confidence, "high")
        self.assertGreaterEqual(result.deal_quality_score, 0.0)
        self.assertLessEqual(result.deal_quality_score, 100.0)
        self.assertIn("Flipkart", result.reasoning)
        self.assertIn("90-day average", result.reasoning)
        self.assertTrue(any(offer.issuer and "HDFC" in offer.issuer for offer in result.offers))
        self.assertTrue(any(offer.offer_type == "coupon" for offer in result.offers))

    async def test_url_input_resolves_exact_match_and_handles_missing_history(self) -> None:
        result = await find_best_deal(
            "https://www.amazon.in/dp/B0XM5",
            provider=self.priced_provider,
        )

        self.assertEqual(result.best_platform, "Flipkart")
        self.assertEqual(result.best_price, 24990.0)
        self.assertIsNone(result.historical_avg_90d)
        self.assertIsNone(result.price_delta_pct)
        self.assertIn("I do not yet have enough in-memory 90-day price history", result.reasoning)
        self.assertEqual(result.product_name, "Sony WH-1000XM5 Wireless Headphones")
        self.assertIn("Flipkart", result.matched_platforms)
        self.assertIn("Amazon.in", result.matched_platforms)
        self.assertIn(result.data_confidence, {"medium", "high"})

    async def test_missing_live_price_returns_none_instead_of_fabricated_value(self) -> None:
        result = await find_best_deal(
            "Sony WH-1000XM5 Wireless Headphones",
            provider=self.no_price_provider,
        )

        self.assertEqual(result.product_name, "Sony WH-1000XM5 Wireless Headphones")
        self.assertEqual(result.best_platform, "Unavailable")
        self.assertIsNone(result.best_price)
        self.assertEqual(result.data_confidence, "low")
        self.assertIn("no current price could be extracted", result.reasoning.lower())
        self.assertIn("inventing a number", result.reasoning.lower())
        self.assertIn("Amazon.in", result.matched_platforms)


if __name__ == "__main__":
    unittest.main()
