from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class SavingPlans(Base):
    __tablename__ = 'saving_plans'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    goal_amount = Column(Float, nullable=False)
    duration_month = Column(Integer, nullable=False)
    plan_data = Column(JSONB, nullable=False)
    algorithm_used = Column(String, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active = Column(Boolean, nullable=False)
    user = relationship("User", back_populates="saving_plans")