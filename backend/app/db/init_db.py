from app.db.base import Base
from app.db.session import engine
from app.models import User, PurchaseHistory, VerdictHistory, AgentResult


async def init_db() -> None:
    """Create all database tables from SQLAlchemy metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
