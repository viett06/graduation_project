from sqlalchemy import Column, String, Integer, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index= True)

    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200))

    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    permission_roles = relationship("PermissionRole", back_populates="role", cascade="all, delete-orphan")
