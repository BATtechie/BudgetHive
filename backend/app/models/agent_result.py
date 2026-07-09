import uuid
from sqlalchemy import Column, String, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship

from app.db.base import Base, TimestampMixin


class AgentResult(TimestampMixin, Base):
    __tablename__ = "agent_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verdict_id = Column(UUID(as_uuid=True), ForeignKey("verdict_history.id", ondelete="CASCADE"), nullable=False, index=True)
    
    agent_name = Column(String(50), nullable=False) # e.g. 'A1_Financial', 'A2_Need'
    score_contributed = Column(Float, nullable=True) # if applicable
    reasoning = Column(String, nullable=True)
    raw_data = Column(JSON, nullable=True) # Full structured output from the agent

    # Relationships
    verdict = relationship("VerdictHistory", back_populates="agent_results")
