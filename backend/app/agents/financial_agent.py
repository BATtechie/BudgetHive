from pydantic import BaseModel, Field
from typing import Dict, Any

# Define the structured output format for the Financial Agent
class FinancialEvaluation(BaseModel):
    score: float = Field(
        ..., 
        description="Score between 0 and 100. 100 is highly affordable, 0 is unaffordable."
    )
    reasoning: str = Field(
        ..., 
        description="Detailed explanation of the financial impact of this purchase."
    )
    discretionary_income: float = Field(
        ..., 
        description="Remaining money after savings, EMIs, and bills."
    )
    price_to_income_ratio: float = Field(
        ..., 
        description="Percentage of discretionary income consumed by this purchase."
    )

def evaluate_financials(
    user_income: float,
    savings_target: float,
    emis: float,
    bills: float,
    purchase_price: float
) -> FinancialEvaluation:
    """
    Evaluates the financial viability of a purchase.
    Can be run as a deterministic node or combined with an LLM for nuanced commentary.
    """
    # 1. Calculate Discretionary Income
    discretionary_income = user_income - (savings_target + emis + bills)
    
    # 2. Check basic affordability
    if discretionary_income <= 0:
        return FinancialEvaluation(
            score=0.0,
            reasoning="Your fixed expenses and savings targets exceed your monthly income. You have zero discretionary budget.",
            discretionary_income=discretionary_income,
            price_to_income_ratio=0.0
        )
        
    price_to_income_ratio = (purchase_price / discretionary_income) * 100
    
    # 3. Calculate score
    if purchase_price > discretionary_income:
        # Purchase exceeds monthly discretionary budget
        score = max(0.0, 30.0 - (purchase_price - discretionary_income) / 100)
        reasoning = (
            f"This purchase of {purchase_price} exceeds your monthly discretionary income of {discretionary_income:.2f} "
            f"by {(purchase_price - discretionary_income):.2f}. Doing this will eat into your savings target."
        )
    elif price_to_income_ratio > 50:
        # Consumes more than half of discretionary budget
        score = 50.0 - (price_to_income_ratio - 50.0) * 0.4
        reasoning = (
            f"This purchase is affordable but highly significant, consuming {price_to_income_ratio:.1f}% "
            f"of your monthly discretionary income ({discretionary_income:.2f})."
        )
    elif price_to_income_ratio > 10:
        # Modest purchase
        score = 85.0 - (price_to_income_ratio - 10.0) * 0.5
        reasoning = (
            f"This purchase easily fits within your discretionary income, consuming "
            f"{price_to_income_ratio:.1f}% of your budget."
        )
    else:
        # Minor purchase
        score = 95.0
        reasoning = (
            f"Highly affordable purchase. It consumes less than 10% of your discretionary income "
            f"({price_to_income_ratio:.1f}%)."
        )

    return FinancialEvaluation(
        score=score,
        reasoning=reasoning,
        discretionary_income=discretionary_income,
        price_to_income_ratio=price_to_income_ratio
    )
