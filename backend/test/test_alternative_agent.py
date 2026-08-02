import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.alternative_agent import run_alternatives_agent


class StubProvider:
    async def resolve_input(self, product_name_or_url):
        return type("Resolved", (), {
            "product_name": product_name_or_url,
            "search_query": product_name_or_url,
        })()

    async def search_platform(self, platform, query):
        return [
            type("Listing", (), {
                "platform": platform,
                "title": "Vivo V70 5G",
                "url": "https://example.test/vivo-v70",
                "listed_price": 38999.0,
                "offers": [],
            })(),
            type("Listing", (), {
                "platform": platform,
                "title": "Nothing 4a Pro",
                "url": "https://example.test/nothing-4a-pro",
                "listed_price": 42999.0,
                "offers": [],
            })(),
        ]

    async def fetch_listing(self, listing):
        return listing


class TestAlternativeAgentWithStubProvider:
    def test_returns_live_web_data_source(self):
        with patch("app.agents.alternative_agent._get_client", return_value=None):
            result = asyncio.run(run_alternatives_agent(
                product_name="Samsung Galaxy S25 FE",
                category="Smartphones",
                price=55000,
                budget_ceiling=70000,
                provider=StubProvider(),
            ))

        assert result.data_source == "LIVE_WEB"
        assert len(result.alternatives) >= 1
        for alt in result.alternatives:
            assert alt.price <= 70000
            assert alt.price > 0

    def test_score_in_valid_range(self):
        with patch("app.agents.alternative_agent._get_client", return_value=None):
            result = asyncio.run(run_alternatives_agent(
                product_name="Samsung Galaxy S25 FE",
                category="Smartphones",
                price=55000,
                budget_ceiling=70000,
                provider=StubProvider(),
            ))

        assert 0 <= result.score <= 100

    def test_alternatives_have_savings(self):
        with patch("app.agents.alternative_agent._get_client", return_value=None):
            result = asyncio.run(run_alternatives_agent(
                product_name="Samsung Galaxy S25 FE",
                category="Smartphones",
                price=55000,
                budget_ceiling=70000,
                provider=StubProvider(),
            ))

        for alt in result.alternatives:
            assert alt.savings_amount >= 0


class TestAlternativeAgentFallback:
    def test_no_provider_no_client_returns_fallback(self):
        with patch("app.agents.alternative_agent._get_client", return_value=None), \
             patch("app.agents.alternative_agent._search_live_web_listings", return_value=[]):
            result = asyncio.run(run_alternatives_agent(
                product_name="Test Product",
                category="Smartphones",
                price=50000,
                budget_ceiling=60000,
            ))

        assert result.alternatives == []
        assert result.score == 70.0
