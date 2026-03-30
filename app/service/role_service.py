
"""
RoleService - Quản lý Role, Permission và assignment
──────────────────────────────────────────────────────
Thêm mới so với bản cũ:
  - get_user_roles(): lấy roles của user (thiếu trong bản gốc)
  - get_user_roles_and_permissions(): trả về dict để nhúng vào JWT
  - get_role_by_name(): cần cho authController lúc register
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.permissionRole import PermissionRole
from app.models.role import Role
from app.models.userRole import UserRole
from app.repository.role_permission_user_repo import RoleAssignmentRepository
from app.repository.role_repository import RoleRepository
from app.schemas.roleSchema import RoleCreate, RoleUpdate


class RoleService:
    def __init__(self, session: Session):
        self.__role_repo   = RoleRepository(session=session)
        self.__assign_repo = RoleAssignmentRepository(session=session)

    # ── Role CRUD ──────────────────────────────────────────────

    def create_role(self, role_data: RoleCreate) -> Role:
        if self.__role_repo.get_by_name(role_data.name):
            raise ValueError("Role name already exists")
        new_role = Role(**role_data.model_dump())
        return self.__role_repo.create(new_role)

    def get_role_by_name(self, name: str) -> Optional[Role]:
        return self.__role_repo.get_by_name(name)

    def update_role(self, role_id: int, role_data: RoleUpdate) -> Optional[Role]:
        role = self.__role_repo.get_by_id(role_id)
        if not role:
            return None
        for field, value in role_data.model_dump(exclude_unset=True).items():
            setattr(role, field, value)
        self.__role_repo.commit()
        return role

    def list_roles(self, skip: int = 0, limit: int = 100) -> List[Role]:
        return self.__role_repo.get_all(skip, limit)

    def delete_role(self, role_id: int) -> bool:
        role = self.__role_repo.get_by_id(role_id)
        if not role:
            return False
        self.__role_repo.delete(role)
        return True

    # Assignment

    def assign_role_to_user(self, user_id: int, role_id: int, assigned_by: int) -> UserRole:
        existing = self.__assign_repo.get_user_role_link(user_id, role_id)
        if existing:
            return existing
        user_role = UserRole(user_id=user_id, role_id=role_id, assigned_by=assigned_by)
        return self.__assign_repo.add(user_role)

    def assign_permission_to_role(self, role_id: int, permission_id: int) -> PermissionRole:
        existing = self.__assign_repo.get_permission_link(role_id, permission_id)
        if existing:
            return existing
        new_link = PermissionRole(role_id=role_id, permission_id=permission_id)
        return self.__assign_repo.add(new_link)

    # Query helpers cho JWT

    def get_user_roles(self, user_id: int) -> List[Role]:
        """Lấy tất cả roles của user."""
        role_ids = self.__assign_repo.get_role_ids_by_user(user_id)
        if not role_ids:
            return []
        return self.__role_repo.get_by_ids(role_ids)

    def get_user_permissions(self, user_id: int) -> List[Permission]:
        """Lấy tất cả permissions của user (qua roles)."""
        role_ids = self.__assign_repo.get_role_ids_by_user(user_id)
        if not role_ids:
            return []
        return self.__assign_repo.get_permissions_by_role_ids(role_ids)

    def get_user_roles_and_permissions(self, user_id: int) -> Dict[str, Any]:
        """
        Trả về dict để nhúng vào JWT claims.
        Gọi 1 lần lúc login, sau đó đọc từ token — không query DB mỗi request.

        Return:
            {
                "roles": ["admin"],
                "permissions": ["user:read", "user:delete", ...]
            }
        """
        roles       = self.get_user_roles(user_id)
        permissions = self.get_user_permissions(user_id)
        return {
            "roles":       [r.name for r in roles],
            "permissions": [p.name for p in permissions],
        }