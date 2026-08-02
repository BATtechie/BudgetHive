import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.verdict import _decide_agents, _rebalance_weights, _classify, _BASE_WEIGHTS


class TestDecideAgents:
    def test_retail_category_with_history_runs_all_five(self):
        agents, skipped = _decide_agents("Electronics", has_history=True, has_need_input=True)
        assert agents == {"A1_Financial", "A2_Need", "A3_DealHunter", "A4_Alternatives", "A5_RegretPredictor"}
        assert skipped == {}

    def test_non_retail_category_skips_deal_and_alt(self):
        agents, skipped = _decide_agents("Services", has_history=True, has_need_input=True)
        assert "A3_DealHunter" not in agents
        assert "A4_Alternatives" not in agents
        assert "A3_DealHunter" in skipped
        assert "A4_Alternatives" in skipped

    def test_no_history_skips_regret(self):
        agents, skipped = _decide_agents("Electronics", has_history=False, has_need_input=True)
        assert "A5_RegretPredictor" not in agents
        assert "A5_RegretPredictor" in skipped

    def test_no_need_input_skips_need(self):
        agents, skipped = _decide_agents("Electronics", has_history=True, has_need_input=False)
        assert "A2_Need" not in agents
        assert "A2_Need" in skipped

    def test_financial_always_runs(self):
        agents, _ = _decide_agents("Unknown", has_history=False, has_need_input=False)
        assert "A1_Financial" in agents

    def test_minimal_case_only_financial(self):
        agents, skipped = _decide_agents("Custom", has_history=False, has_need_input=False)
        assert agents == {"A1_Financial"}
        assert len(skipped) == 4


class TestRebalanceWeights:
    def test_all_agents_uses_base_weights(self):
        all_agents = set(_BASE_WEIGHTS.keys())
        weights = _rebalance_weights(all_agents)
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_single_agent_gets_full_weight(self):
        weights = _rebalance_weights({"A1_Financial"})
        assert abs(weights["A1_Financial"] - 1.0) < 0.01

    def test_two_agents_proportional(self):
        weights = _rebalance_weights({"A1_Financial", "A2_Need"})
        assert abs(weights["A1_Financial"] - weights["A2_Need"]) < 0.01
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_skipped_agent_weight_redistributed(self):
        agents = {"A1_Financial", "A2_Need", "A3_DealHunter"}
        weights = _rebalance_weights(agents)
        assert "A4_Alternatives" not in weights
        assert "A5_RegretPredictor" not in weights
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestClassify:
    def test_buy(self):
        assert _classify(75) == "BUY"

    def test_maybe(self):
        assert _classify(55) == "MAYBE"

    def test_skip(self):
        assert _classify(30) == "SKIP"

    def test_boundary_buy(self):
        assert _classify(70) == "BUY"

    def test_boundary_maybe(self):
        assert _classify(40) == "MAYBE"

    def test_boundary_skip(self):
        assert _classify(39.9) == "SKIP"
