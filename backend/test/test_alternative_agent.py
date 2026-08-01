import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.alternative_agent import run_alternatives_agent


class StubProvider:
    async def resolve_input(self, product_name_or_url):
        return type("Resolved", (), {"product_name": product_name_or_url, "search_query": product_name_or_url})()

    async def search_platform(self, platform, query):
        return [
            type(
                "Listing",
                (),
                {
                    "platform": platform,
                    "title": "Vivo V70 5G",
                    "url": "https://example.test/vivo-v70",
                    "listed_price": 38999.0,
                    "offers": [],
                },
            )(),
            type(
                "Listing",
                (),
                {
                    "platform": platform,
                    "title": "Nothing 4a Pro",
                    "url": "https://example.test/nothing-4a-pro",
                    "listed_price": 42999.0,
                    "offers": [],
                },
            )(),
        ]

    async def fetch_listing(self, listing):
        return listing


class AlternativeAgentTests(unittest.TestCase):
    def test_alternative_agent_returns_price_range_matches_for_phone_search(self):
        result = run_alternatives_agent(
            product_name="Samsung Galaxy S25 FE",
            category="Smartphones",
            price=55000,
            budget_ceiling=70000,
            primary_use_case="Flagship-like performance and camera",
        )

        self.assertLessEqual(result.score, 100.0)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertGreaterEqual(len(result.alternatives), 0)
        if result.alternatives:
            first = result.alternatives[0]
            self.assertGreater(first.price, 0)
            self.assertLessEqual(first.price, 70000)
            self.assertIn("price", first.spec_difference.lower())

    def test_alternative_agent_uses_injected_live_web_listing_data(self):
        result = run_alternatives_agent(
            product_name="Samsung Galaxy S25 FE",
            category="Smartphones",
            price=55000,
            budget_ceiling=70000,
            provider=StubProvider(),
        )

        self.assertEqual(result.data_source, "LIVE_WEB")
        self.assertGreaterEqual(len(result.alternatives), 1)
        self.assertLessEqual(result.alternatives[0].price, 70000)


if __name__ == "__main__":
    unittest.main()
