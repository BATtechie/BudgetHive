import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if "google" not in sys.modules:
    google_module = types.ModuleType("google")
    genai_module = types.ModuleType("google.genai")

    class DummyClient:
        pass

    class DummyTypes:
        class GenerateContentConfig:
            def __init__(self, *args, **kwargs):
                pass

        class ThinkingConfig:
            def __init__(self, *args, **kwargs):
                pass

    genai_module.Client = DummyClient
    genai_module.types = DummyTypes
    google_module.genai = genai_module
    sys.modules["google"] = google_module
    sys.modules["google.genai"] = genai_module

MODULE_PATH = BACKEND_DIR / "app" / "agents" / "need_agent.py"
SPEC = importlib.util.spec_from_file_location("need_agent_under_test", MODULE_PATH)
need_agent = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = need_agent
SPEC.loader.exec_module(need_agent)


class NeedAgentTests(unittest.TestCase):
    def test_generate_questions_returns_fallback_when_client_is_unavailable(self):
        with patch("app.agents.need_agent._get_client", return_value=None):
            result = need_agent.generate_questions(
                product_name="Noise cancelling headphones",
                category="Electronics",
                price=5000,
            )

        self.assertEqual(len(result.questions), 3)
        self.assertIn("Do you already own", result.questions[0].question)
        self.assertEqual(
            result.reason_for_asking,
            "Your answers help us give you an accurate, personalised verdict.",
        )

    def test_evaluate_need_from_answers_falls_back_without_llm_client(self):
        with patch("app.agents.need_agent._get_client", return_value=None):
            result = need_agent.evaluate_need_from_answers(
                product_name="Noise cancelling headphones",
                category="Electronics",
                price=5000,
                user_answers={
                    "What will you use them for?": "I need them for work calls",
                    "How often will you use them?": "Every day",
                },
            )

        self.assertEqual(result.data_source, "FALLBACK")
        self.assertEqual(result.classification, need_agent.NeedClassification.MODERATE_WANT)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)

    def test_run_need_agent_routes_to_history_path_and_returns_fallback(self):
        with patch("app.agents.need_agent._get_client", return_value=None):
            result = need_agent.run_need_agent(
                product_name="Noise cancelling headphones",
                category="Electronics",
                price=5000,
                purchase_history_summary="Bought 2 similar products in the last 6 months",
            )

        self.assertEqual(result.data_source, "FALLBACK")
        self.assertEqual(result.classification, need_agent.NeedClassification.MODERATE_WANT)


if __name__ == "__main__":
    unittest.main()
