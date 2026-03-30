from sqlalchemy import Column, Integer, String, Table, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime, timezone
from sqlalchemy.sql import func

class User(Base):
    __tablename__= "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(200), unique= True, index= True, nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    hashed_password = Column(String(200), nullable= False)
    is_active = Column(Boolean, default= True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan",  passive_deletes=True)


