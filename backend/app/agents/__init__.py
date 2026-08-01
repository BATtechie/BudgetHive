# LangGraph agent definitions
# A1-A5 specialist agents, A6 Final Judge, and Orchestrator

from app.agents.financial_agent import (
    FinancialEvaluation,
    evaluate_financials,
)
from app.agents.need_agent import (
    NeedClassification,
    NeedEvaluation,
    NeedQuestions,
    ClarifyingQuestion,
    generate_questions,
    evaluate_need_from_answers,
    evaluate_need_from_history,
    run_need_agent,
)

from app.agents.deal_hunter_agent import (
    OfferDetail,
    DealHunterResult,
    PriceSourceProvider,
    WebPriceSourceProvider,
    find_best_deal,
    run_deal_hunter_agent,
)
from app.agents.alternative_agent import (
    Alternative,
    AlternativeType,
    AlternativesEvaluation,
    run_alternatives_agent,
)

__all__ = [
    "FinancialEvaluation",
    "evaluate_financials",
    "NeedClassification",
    "NeedEvaluation",
    "NeedQuestions",
    "ClarifyingQuestion",
    "generate_questions",
    "evaluate_need_from_answers",
    "evaluate_need_from_history",
    "run_need_agent",
    "OfferDetail",
    "DealHunterResult",
    "PriceSourceProvider",
    "WebPriceSourceProvider",
    "find_best_deal",
    "run_deal_hunter_agent",
    "Alternative",
    "AlternativeType",
    "AlternativesEvaluation",
    "run_alternatives_agent",
]
