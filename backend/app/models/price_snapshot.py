import uuid
from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

from app.db.base import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_identifier = Column(String(300), nullable=False, index=True)
    price = Column(Float, nullable=False)
    platform = Column(String(100), nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_price_snapshots_product_checked", "product_identifier", "checked_at"),
    )
