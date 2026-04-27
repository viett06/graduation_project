# app/models/crawler_log.py
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class CrawlerLog(Base):
    __tablename__ = "crawler_logs"
    id = Column(Integer, primary_key=True)
    bank_id = Column(Integer, ForeignKey("banks.id"))
    status = Column(String(20))   # success, failed, skipped
    rates_found = Column(Integer)
    rates_updated = Column(Integer)
    rates_created = Column(Integer)
    error_message = Column(Text)
    execution_time_seconds = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())