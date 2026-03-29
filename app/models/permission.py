from sqlalchemy import String, Column, Index, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Permission(Base):
    __tablename__= "permissions"

    id= Column(Integer, primary_key= True, index=True)
    name=Column(String(100), unique=True, nullable=False)
    resource= Column(String(50))
    action = Column(String(50))

    permission_roles = relationship("PermissionRole", back_populates="permission", cascade="all, delete-orphan")

