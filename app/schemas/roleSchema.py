# app/schemas/role.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class PermissionSimpleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class PermissionRoleOut(BaseModel):
    id: int
    permission_id: int
    # Pydantic sẽ tự gọi getattr(permission_role_item, "permission")
    permission: PermissionSimpleOut

    model_config = ConfigDict(from_attributes=True)


class RoleInDBBase(RoleBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RoleResponse(RoleInDBBase):
    permission_roles: List[PermissionRoleOut] = []
