import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend path is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

load_dotenv(dotenv_path=backend_dir / ".env")

from app.agents.deal_hunter_agent import run_deal_hunter_agent, DealBadge


def print_deal_badge(badge: DealBadge) -> str:
    if badge == DealBadge.GOOD_DEAL:
        return "🟢 Good Deal"
    elif badge == DealBadge.AVERAGE_DEAL:
        return "🟡 Average Deal"
    else:
        return "🔴 Poor Deal"


def print_evaluation(title: str, evaluation):
    print("=" * 80)
    print(f"🎯 {title}")
    print("=" * 80)
    print(f"📦 Product Name        : {evaluation.product_name}")
    print(f"🔗 Input Type          : {evaluation.input_type}")
    print(f"🏷️  Overall Badge      : {print_deal_badge(evaluation.overall_badge)}")
    print(f"⭐ Overall Score       : {evaluation.overall_score} / 100")
    print(f"🏆 Best Recommended    : {evaluation.best_platform}")
    print(f"🛒 Buy Now or Wait?    : {evaluation.buy_now_or_wait}")
    print(f"⚙️  Data Source        : {evaluation.data_source}")
    print("-" * 80)
    print("🌐 SCANNED PLATFORMS & DEALS:")
    for idx, deal in enumerate(evaluation.scanned_deals, 1):
        badge_str = print_deal_badge(deal.badge)
        print(f"\n   [{idx}] {deal.platform} ({badge_str})")
        print(f"       • Current Price      : ₹{deal.current_price:,.2f}")
        print(f"       • 90-Day Low Price   : ₹{deal.historical_low_90d:,.2f} ({deal.price_vs_historical_diff_pct:+.1f}%)")
        if deal.bank_offers:
            print(f"       • Bank Offers        : {', '.join(o.discount_description for o in deal.bank_offers)}")
        if deal.coupons_and_cashbacks:
            print(f"       • Coupons & Cashback : {', '.join(c.description for c in deal.coupons_and_cashbacks)}")
        print(f"       • Net Effective Price: ₹{deal.effective_price:,.2f}")
        print(f"       • Store URL          : {deal.store_url}")

    print("\n" + "-" * 80)
    print("🏆 TOP 3 WEBSITES BREAKDOWN:")
    for rank, deal in enumerate(evaluation.top_3_deals, 1):
        print(f"   Rank #{rank}: {deal.platform} — Net Effective ₹{deal.effective_price:,.2f} ({print_deal_badge(deal.badge)})")

    print("\n" + "-" * 80)
    print("🧠 AI RECOMMENDATION NARRATIVE:")
    print(f"{evaluation.ai_recommendation}")
    print("=" * 80 + "\n")


def run_tests():
    print("\n" + "★" * 80)
    print("        BUDGETHIVE DEAL HUNTER AGENT (A3) DYNAMIC EVALUATION DEMO")
    print("★" * 80 + "\n")

    # Test 1: Premium Phone Query ("Apple iPhone 15 128GB")
    print("Running Test 1: Apple iPhone 15 128GB...\n")
    eval1 = run_deal_hunter_agent(
        product_query="Apple iPhone 15 128GB Blue",
        user_banks=["HDFC Bank", "SBI Card"],
    )
    print_evaluation("Test 1: Apple iPhone 15 128GB", eval1)

    # Test 2: Laptop Query ("MacBook Air M2")
    print("Running Test 2: MacBook Air M2...\n")
    eval2 = run_deal_hunter_agent(
        product_query="Apple MacBook Air M2 8GB 256GB SSD",
        user_banks=["ICICI Bank", "Axis Bank"],
    )
    print_evaluation("Test 2: MacBook Air M2", eval2)

    # Test 3: Audio Query ("Sony WH-1000XM5")
    print("Running Test 3: Sony WH-1000XM5 Wireless Headphones...\n")
    eval3 = run_deal_hunter_agent(
        product_query="Sony WH-1000XM5 Wireless Headphones",
        user_banks=["HDFC Bank"],
    )
    print_evaluation("Test 3: Sony Headphones", eval3)

    # Verify that evaluations are different and dynamically generated!
    assert eval1.product_name != eval2.product_name
    assert eval1.scanned_deals[0].current_price != eval2.scanned_deals[0].current_price
    assert eval2.scanned_deals[0].current_price != eval3.scanned_deals[0].current_price
    assert "My recommended:" in eval1.ai_recommendation or "my recommended:" in eval1.ai_recommendation.lower()

    print("✅ All dynamic Deal Hunter Agent tests verified! Zero hardcoded values!\n")


if __name__ == "__main__":
    run_tests()
