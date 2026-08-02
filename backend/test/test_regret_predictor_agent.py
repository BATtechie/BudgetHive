import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.regret_predictor_agent import (
    predict_regret,
    RegretPrediction,
    RegretRiskLevel,
    _fallback_from_scores,
    _classify_risk,
)


class TestClassifyRisk:
    def test_high_risk(self):
        assert _classify_risk(80) == RegretRiskLevel.HIGH

    def test_medium_risk(self):
        assert _classify_risk(50) == RegretRiskLevel.MEDIUM

    def test_low_risk(self):
        assert _classify_risk(20) == RegretRiskLevel.LOW

    def test_boundary_high(self):
        assert _classify_risk(65) == RegretRiskLevel.HIGH

    def test_boundary_medium(self):
        assert _classify_risk(35) == RegretRiskLevel.MEDIUM


class TestFallbackFromScores:
    def test_low_financial_low_need_high_regret(self):
        result = _fallback_from_scores(20.0, 20.0)
        assert result.regret_score == 80.0
        assert result.risk_level == RegretRiskLevel.HIGH
        assert result.data_source == "FORMULA_FALLBACK"

    def test_high_financial_high_need_low_regret(self):
        result = _fallback_from_scores(90.0, 90.0)
        assert result.regret_score == 10.0
        assert result.risk_level == RegretRiskLevel.LOW

    def test_none_scores_default_to_50(self):
        result = _fallback_from_scores(None, None)
        assert result.regret_score == 50.0
        assert result.risk_level == RegretRiskLevel.MEDIUM

    def test_mixed_scores(self):
        result = _fallback_from_scores(80.0, 30.0)
        expected = round(100.0 - (0.6 * 80 + 0.4 * 30), 1)
        assert result.regret_score == expected

    def test_clamped_to_bounds(self):
        result = _fallback_from_scores(100.0, 100.0)
        assert 0 <= result.regret_score <= 100

    def test_reasons_low_financial(self):
        result = _fallback_from_scores(20.0, 80.0)
        assert any("financial" in r.lower() for r in result.reasons)

    def test_reasons_low_need(self):
        result = _fallback_from_scores(80.0, 20.0)
        assert any("need" in r.lower() for r in result.reasons)


class TestPredictRegret:
    def test_falls_back_when_no_api_key(self):
        with patch("app.agents.regret_predictor_agent._get_client", return_value=None):
            result = predict_regret(
                product_name="Test Product",
                category="Electronics",
                price=5000,
                financial_score=70.0,
                need_score=60.0,
            )
        assert isinstance(result, RegretPrediction)
        assert result.data_source == "FORMULA_FALLBACK"
        assert 0 <= result.regret_score <= 100

    def test_llm_parse_error_falls_back(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "not valid json"
        mock_client.models.generate_content.return_value = mock_response

        with patch("app.agents.regret_predictor_agent._get_client", return_value=mock_client):
            with patch("app.agents.regret_predictor_agent.generate_content_with_fallback", return_value=mock_response):
                result = predict_regret(
                    product_name="Test",
                    category="Electronics",
                    price=5000,
                    financial_score=50.0,
                    need_score=50.0,
                )
        assert result.data_source == "FORMULA_FALLBACK"

    def test_llm_success(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"regret_score": 35, "risk_level": "MEDIUM", "reasons": ["moderate price"], "confidence": 75, "data_source": "LLM_ONLY"}'

        with patch("app.agents.regret_predictor_agent._get_client", return_value=mock_client):
            with patch("app.agents.regret_predictor_agent.generate_content_with_fallback", return_value=mock_response):
                result = predict_regret(
                    product_name="Test",
                    category="Electronics",
                    price=5000,
                )
        assert result.regret_score == 35.0
        assert result.risk_level == RegretRiskLevel.MEDIUM
        assert result.data_source == "LLM_ONLY"

    def test_with_history_sets_data_source(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"regret_score": 60, "risk_level": "MEDIUM", "reasons": ["past returns"], "confidence": 80, "data_source": "HISTORY_AND_LLM"}'

        with patch("app.agents.regret_predictor_agent._get_client", return_value=mock_client):
            with patch("app.agents.regret_predictor_agent.generate_content_with_fallback", return_value=mock_response):
                result = predict_regret(
                    product_name="Test",
                    category="Electronics",
                    price=5000,
                    history_summary="User returned 2 of 3 past Electronics purchases.",
                )
        assert result.data_source == "HISTORY_AND_LLM"

    def test_score_clamped(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"regret_score": 150, "risk_level": "HIGH", "reasons": ["very bad"], "confidence": 200, "data_source": "LLM_ONLY"}'

        with patch("app.agents.regret_predictor_agent._get_client", return_value=mock_client):
            with patch("app.agents.regret_predictor_agent.generate_content_with_fallback", return_value=mock_response):
                result = predict_regret(
                    product_name="Test",
                    category="Electronics",
                    price=5000,
                )
        assert result.regret_score == 100.0
        assert result.confidence == 100.0
