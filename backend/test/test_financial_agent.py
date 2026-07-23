import os
import sys
from dotenv import load_dotenv

# Load env variables from backend/.env
load_dotenv()

from app.agents.financial_agent import evaluate_financials

def print_result(title, result):
    print("=" * 70)
    print(f"🔹 {title}")
    print("-" * 70)
    print(f"💰 Score                 : {result.score} / 100")
    print(f"💳 Discretionary Income  : ₹{result.discretionary_income:,.2f}")
    print(f"📊 Budget Consumed       : {result.price_to_income_ratio:.1f}%")
    print(f"⚙️  Evaluator Source     : {result.data_source}")
    print(f"📝 Reasoning:\n   \"{result.reasoning}\"")
    print("=" * 70)
    print()

def run_demo():
    print("\n" + "★" * 70)
    print("      BUDGETHIVE FINANCIAL AGENT DEMO & COMPARISON")
    print("★" * 70 + "\n")

    # Scenario 1: A massive purchase that exceeds the budget
    # Income: 80,000, Savings target: 30,000, EMIs: 15,000, Bills: 20,000
    # Remaining Discretionary: 15,000
    # Purchase Price: 40,000 (Buying an expensive laptop)
    laptop_purchase = {
        "user_income": 80000,
        "savings_target": 30000,
        "emis": 15000,
        "bills": 20000,
        "purchase_price": 40000
    }

    # Scenario 2: A modest purchase that fits comfortable but requires caution
    # Income: 80,000, Savings target: 30,000, EMIs: 15,000, Bills: 20,000
    # Remaining Discretionary: 15,000
    # Purchase Price: 5,000 (Buying premium headphones)
    headphones_purchase = {
        "user_income": 80000,
        "savings_target": 30000,
        "emis": 15000,
        "bills": 20000,
        "purchase_price": 5000
    }

    print("--- RUNNING DETEMINISTIC RULES (NO LLM) ---")
    res1_rule = evaluate_financials(**laptop_purchase, use_llm=False)
    print_result("Deterministic Rules: High Expense (Laptop)", res1_rule)

    res2_rule = evaluate_financials(**headphones_purchase, use_llm=False)
    print_result("Deterministic Rules: Moderate Expense (Headphones)", res2_rule)

    # Check if API Key is configured
    from app.config import settings
    api_key = settings.GEMINI_API_KEY
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n⚠️  Notice: GEMINI_API_KEY is not configured in .env.")
        print("   The demo below will fall back to rule-based evaluation.")
        print("   Configure a real key in .env to see the thinking LLM agent in action!\n")
    else:
        print("\n✨ Running with Thinking LLM (Gemini 2.5 Flash)!\n")

    print("--- RUNNING LLM / THINKING MODEL EVALUATOR ---")
    res1_llm = evaluate_financials(**laptop_purchase, use_llm=True)
    print_result("LLM (Thinking): High Expense (Laptop)", res1_llm)

    res2_llm = evaluate_financials(**headphones_purchase, use_llm=True)
    print_result("LLM (Thinking): Moderate Expense (Headphones)", res2_llm)

if __name__ == "__main__":
    run_demo()
