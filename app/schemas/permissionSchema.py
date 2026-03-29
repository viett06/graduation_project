# app/schemas/permission.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List


class PermissionBase(BaseModel):
    name: str
    resource: str
    action: str


class PermissionCreate(PermissionBase):
    pass


class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None


class PermissionRoleOut(BaseModel):
    id: int
    role_id: int
    role_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PermissionInDBBase(PermissionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PermissionResponse(PermissionInDBBase):
    permission_roles: List[PermissionRoleOut] = []