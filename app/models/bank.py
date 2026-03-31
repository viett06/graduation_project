from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.sql import func

class Bank(Base):
    __tablename__ = "banks"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False, unique=True)
    code = Column(String, nullable=False, unique=True)
    type = Column(String, nullable=False, unique=True)
    logo_url = Column(String)
    website_url = Column(String)
    rate_source = Column(String)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at =Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

