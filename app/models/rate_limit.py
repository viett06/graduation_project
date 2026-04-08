from sqlalchemy import Column, Integer, String

from app.db.base import Base


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True)

    rate_limit_capacity = Column(Integer)
    refill_rate = Column(Integer)
    window_time = Column(Integer)
    max_limit_second = Column(Integer)
    max_limit_minutes = Column(Integer)
    path = Column(String)
    method = Column(String)



