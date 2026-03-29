from sqlalchemy import String, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class PermissionRole(Base):

    __tablename__ = "permission_roles"
    
    id = Column(Integer, primary_key=True)

    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable= False)
    role_id = Column(Integer, ForeignKey("roles.id"),nullable=False)

    permission = relationship("Permission", back_populates="permission_roles")
    role = relationship("Role", back_populates="permission_roles")
