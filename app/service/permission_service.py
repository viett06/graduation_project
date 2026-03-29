from typing import Optional, List
from app.models.permission import Permission
from app.schemas.permissionSchema import PermissionCreate, PermissionUpdate
from app.repository.permission_repository import PermissionRepository


class PermissionService:
    def __init__(self, repository: PermissionRepository):
        self.repository = repository

    def create_permission(self, permission_data: PermissionCreate) -> Permission:

        existing = self.repository.get_by_name(permission_data.name)
        if existing:
            raise ValueError("Permission name already exists")

        # Dictionary Unpacking
        new_permission = Permission(**permission_data.model_dump())
        return self.repository.create(new_permission)

    def get_permission(self, permission_id: int) -> Optional[Permission]:

        permission = self.repository.get_by_id(permission_id)
        if not permission:
            return None
        return permission

    def list_permissions(self, skip: int = 0, limit: int = 100) -> List[Permission]:
        return self.repository.get_all(skip, limit)

    def update_permission(self, permission_id: int, permission_data: PermissionUpdate) -> Optional[Permission]:
        permission = self.repository.get_by_id(permission_id)
        if not permission:
            return None

        update_data = permission_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(permission, field, value)

        self.repository.update()
        return permission

    def delete_permission(self, permission_id: int) -> bool:
        permission = self.repository.get_by_id(permission_id)
        if not permission:
            return False

        self.repository.delete(permission)
        return True