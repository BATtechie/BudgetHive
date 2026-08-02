import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.financial_agent import evaluate_financials, FinancialEvaluation


class TestDeterministicFinancials:
    def test_exceeds_budget_scores_low(self):
        result = evaluate_financials(
            user_income=80000, savings_target=30000, emis=15000,
            bills=20000, purchase_price=40000, use_llm=False,
        )
        assert isinstance(result, FinancialEvaluation)
        assert result.data_source == "RULE_BASED"
        assert result.discretionary_income == 15000.0
        assert result.score < 30
        assert "exceeds" in result.reasoning.lower()

    def test_moderate_purchase_scores_mid(self):
        result = evaluate_financials(
            user_income=80000, savings_target=30000, emis=15000,
            bills=20000, purchase_price=5000, use_llm=False,
        )
        assert result.data_source == "RULE_BASED"
        assert result.discretionary_income == 15000.0
        expected_ratio = (5000 / 15000) * 100
        assert abs(result.price_to_income_ratio - round(expected_ratio, 2)) < 0.01
        assert 60 < result.score < 90

    def test_cheap_purchase_scores_high(self):
        result = evaluate_financials(
            user_income=100000, savings_target=20000, emis=0,
            bills=10000, purchase_price=500, use_llm=False,
        )
        assert result.score == 95.0
        assert result.discretionary_income == 70000.0

    def test_zero_discretionary_income_scores_zero(self):
        result = evaluate_financials(
            user_income=50000, savings_target=30000, emis=15000,
            bills=10000, purchase_price=5000, use_llm=False,
        )
        assert result.score == 0.0
        assert result.discretionary_income <= 0

    def test_score_clamped_to_0_100(self):
        result = evaluate_financials(
            user_income=80000, savings_target=30000, emis=15000,
            bills=20000, purchase_price=500000, use_llm=False,
        )
        assert 0 <= result.score <= 100

    def test_over_50_percent_ratio_path(self):
        result = evaluate_financials(
            user_income=80000, savings_target=30000, emis=15000,
            bills=20000, purchase_price=10000, use_llm=False,
        )
        ratio = (10000 / 15000) * 100
        assert ratio > 50
        assert result.score < 50


class TestLLMFallback:
    def test_use_llm_falls_back_when_no_api_key(self):
        with patch("app.agents.financial_agent._get_client", return_value=None):
            result = evaluate_financials(
                user_income=80000, savings_target=30000, emis=15000,
                bills=20000, purchase_price=5000, use_llm=True,
            )
        assert result.data_source == "RULE_BASED"
        assert 0 <= result.score <= 100
