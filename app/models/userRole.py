from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class UserRole(Base):
    __tablename__="user_roles"


    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable= False)
    role_id = Column(Integer, ForeignKey("roles.id"),nullable=False)

    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(Integer, nullable=True)

    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")