from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.sql import func


class InterestRate(Base):
    __tablename__ = 'interest_rates'
    id = Column(Integer, primary_key=True)
    min_amount = Column(Integer)
    max_amount = Column(Integer)
    term_month = Column(Integer, nullable=False)
    rate = Column(Numeric(precision=10, scale=4), nullable=False)
    effective_date = Column(DateTime, nullable=False)
    is_current = Column(Boolean, nullable=False)
    note = Column(Text)
    create_by = Column(Integer, ForeignKey("users.id",ondelete="SET NULL"), nullable=True)
    bank_id = Column(Integer, ForeignKey("banks.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    bank = relationship("Bank", back_populates="interest_rates")




