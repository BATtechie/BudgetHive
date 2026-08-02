"""
Seed script — creates a demo user + purchase history + verdict history.

Usage:
    cd backend && python seed.py

Demo credentials:
    Email:    demo@budgethive.com
    Password: demo1234
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from app.db.session import engine, async_session
from app.db.base import Base
from app.models.user import User
from app.models.purchase_history import PurchaseHistory
from app.models.verdict_history import VerdictHistory
from app.models.agent_result import AgentResult
from app.core.security import hash_password

DEMO_EMAIL = "demo@budgethive.com"
DEMO_PASSWORD = "demo1234"

now = datetime.now(timezone.utc)


async def seed():
    async with async_session() as session:
        existing = await session.execute(select(User).where(User.email == DEMO_EMAIL))
        if existing.scalar_one_or_none():
            print(f"Demo user ({DEMO_EMAIL}) already exists — skipping.")
            return

        user = User(
            id=uuid.uuid4(),
            name="Aarav Sharma",
            email=DEMO_EMAIL,
            password=hash_password(DEMO_PASSWORD),
            monthly_income=85000.0,
            monthly_savings_target=20000.0,
            active_emis=12000.0,
            recurring_bills=8500.0,
        )
        session.add(user)
        await session.flush()

        purchases = [
            PurchaseHistory(
                user_id=user.id,
                product_name="Apple AirPods Pro 2",
                product_category="Earphones",
                purchase_price=24900.0,
                usage_duration_days=180,
                is_returned=False,
                is_resold=False,
                regret_score=10,
            ),
            PurchaseHistory(
                user_id=user.id,
                product_name="Samsung Galaxy S24 Ultra",
                product_category="Smartphones",
                purchase_price=129999.0,
                usage_duration_days=90,
                is_returned=False,
                is_resold=False,
                regret_score=25,
            ),
            PurchaseHistory(
                user_id=user.id,
                product_name="IKEA MARKUS Office Chair",
                product_category="Furniture",
                purchase_price=14990.0,
                usage_duration_days=365,
                is_returned=False,
                is_resold=False,
                regret_score=5,
            ),
            PurchaseHistory(
                user_id=user.id,
                product_name="Noise ColorFit Pro 4",
                product_category="Smartwatches",
                purchase_price=3499.0,
                usage_duration_days=60,
                is_returned=False,
                is_resold=True,
                regret_score=70,
            ),
            PurchaseHistory(
                user_id=user.id,
                product_name="Kindle Paperwhite 5",
                product_category="Electronics",
                purchase_price=13999.0,
                usage_duration_days=200,
                is_returned=False,
                is_resold=False,
                regret_score=8,
            ),
            PurchaseHistory(
                user_id=user.id,
                product_name="boAt Rockerz 550",
                product_category="Headphones",
                purchase_price=1799.0,
                usage_duration_days=30,
                is_returned=True,
                is_resold=False,
                regret_score=85,
            ),
            PurchaseHistory(
                user_id=user.id,
                product_name="Sony PS5 Digital Edition",
                product_category="Gaming Consoles",
                purchase_price=39990.0,
                usage_duration_days=150,
                is_returned=False,
                is_resold=False,
                regret_score=15,
            ),
        ]

        for p in purchases:
            session.add(p)

        verdicts_data = [
            {
                "product_name": "Sony WH-1000XM5",
                "product_category": "Headphones",
                "verdict": "BUY",
                "composite_score": 78.5,
                "confidence_percentage": 87.0,
                "days_ago": 2,
                "agents": [
                    ("A1_Financial", 82.0, "Price ₹26,990 is within your disposable surplus of ₹44,500. Safe to spend."),
                    ("A2_Need", 71.0, "You returned your last headphones. A quality upgrade addresses a real gap."),
                    ("A3_DealHunter", 75.0, "Current price is near 90-day low. No major sale expected in the next 2 weeks."),
                    ("A4_Alternatives", 80.0, "Top alternative: Bose QC Ultra at ₹29,990. Sony offers better value at this price."),
                ],
            },
            {
                "product_name": "MacBook Air M3",
                "product_category": "Laptops",
                "verdict": "MAYBE",
                "composite_score": 55.2,
                "confidence_percentage": 74.0,
                "days_ago": 5,
                "agents": [
                    ("A1_Financial", 38.0, "At ₹1,14,900, this exceeds your monthly disposable by 2.5x. Consider EMI or saving."),
                    ("A2_Need", 68.0, "No laptop in purchase history. Could be a genuine need, but impulse probability is moderate."),
                    ("A3_DealHunter", 60.0, "Student discount available. Apple Back-to-School sale expected in June."),
                    ("A4_Alternatives", 55.0, "HP Pavilion Plus at ₹74,990 offers similar performance for less."),
                ],
            },
            {
                "product_name": "Dyson V15 Detect",
                "product_category": "Appliances",
                "verdict": "SKIP",
                "composite_score": 32.0,
                "confidence_percentage": 91.0,
                "days_ago": 8,
                "agents": [
                    ("A1_Financial", 22.0, "At ₹62,900, this is 141% of your monthly disposable. Very risky for a non-essential."),
                    ("A2_Need", 35.0, "No cleaning appliance in history. Impulse probability: 76%. Similar to your smartwatch regret pattern."),
                    ("A5_RegretPredictor", 40.0, "Based on past high-regret purchases in impulse categories, estimated regret: 68%."),
                ],
            },
            {
                "product_name": "Samsung Galaxy S25 Ultra",
                "product_category": "Smartphones",
                "verdict": "MAYBE",
                "composite_score": 48.0,
                "confidence_percentage": 82.0,
                "days_ago": 12,
                "agents": [
                    ("A1_Financial", 30.0, "At ₹1,34,999, this is 3x your monthly disposable. High financial strain."),
                    ("A2_Need", 42.0, "You bought Galaxy S24 Ultra 90 days ago. Upgrade cycle too short."),
                    ("A3_DealHunter", 65.0, "Trade-in offer of ₹40,000 available. Effective price: ₹94,999."),
                    ("A4_Alternatives", 55.0, "iPhone 16 Pro Max at ₹1,44,900 or Pixel 9 Pro at ₹1,09,999."),
                    ("A5_RegretPredictor", 48.0, "Low regret on S24 Ultra purchase (25/100), but upgrading in 90 days is a pattern flag."),
                ],
            },
            {
                "product_name": "Kindle Scribe",
                "product_category": "Electronics",
                "verdict": "BUY",
                "composite_score": 82.0,
                "confidence_percentage": 90.0,
                "days_ago": 15,
                "agents": [
                    ("A1_Financial", 88.0, "At ₹23,999, well within disposable surplus. Low financial risk."),
                    ("A2_Need", 79.0, "You own a Kindle Paperwhite with 200 days of use and very low regret (8/100). Proven reader."),
                    ("A3_DealHunter", 72.0, "Price steady. Amazon Great Indian Festival in 6 weeks may drop 10-15%."),
                    ("A4_Alternatives", 85.0, "reMarkable 2 at ₹42,000 is significantly more expensive. Scribe is best value."),
                    ("A5_RegretPredictor", 88.0, "Very low regret predicted based on your reading device satisfaction history."),
                ],
            },
        ]

        for vd in verdicts_data:
            verdict = VerdictHistory(
                id=uuid.uuid4(),
                user_id=user.id,
                product_name=vd["product_name"],
                product_category=vd["product_category"],
                verdict=vd["verdict"],
                composite_score=vd["composite_score"],
                confidence_percentage=vd["confidence_percentage"],
            )
            verdict.created_at = now - timedelta(days=vd["days_ago"])
            session.add(verdict)
            await session.flush()

            for agent_name, score, reasoning in vd["agents"]:
                ar = AgentResult(
                    id=uuid.uuid4(),
                    verdict_id=verdict.id,
                    agent_name=agent_name,
                    score_contributed=score,
                    reasoning=reasoning,
                )
                session.add(ar)

        await session.commit()
        print(f"Seeded demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"Seeded {len(purchases)} purchase history entries.")
        print(f"Seeded {len(verdicts_data)} verdict history entries.")


if __name__ == "__main__":
    asyncio.run(seed())
