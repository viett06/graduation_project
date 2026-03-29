from sqlalchemy.orm import Session
from typing import List
from app.models.userRole import UserRole
from app.models.permissionRole import PermissionRole
from app.models.permission import Permission

class RoleAssignmentRepository:
    def __init__(self, session: Session):
        self.session = session

    # --- Permission Role Methods ---
    def get_permission_link(self, role_id: int, permission_id: int):
        return self.session.query(PermissionRole).filter(
            PermissionRole.role_id == role_id,
            PermissionRole.permission_id == permission_id
        ).first()

    def get_permissions_by_role_ids(self, role_ids: List[int]) -> List[Permission]:
        return self.session.query(Permission).join(PermissionRole).filter(
            PermissionRole.role_id.in_(role_ids)
        ).all()

    # --- User Role Methods ---
    def get_user_role_link(self, user_id: int, role_id: int):
        return self.session.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id
        ).first()

    def get_role_ids_by_user(self, user_id: int) -> List[int]:
        user_roles = self.session.query(UserRole).filter(UserRole.user_id == user_id).all()
        return [ur.role_id for ur in user_roles]

    def add(self, obj):
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def delete(self, obj):
        self.session.delete(obj)
        self.session.commit()