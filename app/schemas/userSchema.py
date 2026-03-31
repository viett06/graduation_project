# app/schemas/user.py
from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List


class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None

class PermissionOut(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class PermissionRoleOut(BaseModel):
    permission: PermissionOut

    model_config = ConfigDict(from_attributes=True)

class RoleSimpleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    permission_roles: List[PermissionRoleOut] = []
    model_config = ConfigDict(from_attributes=True)


class UserRoleOut(BaseModel):
    id: int  # ID của bản ghi mapping
    assigned_at: datetime
    # Lấy object role từ relationship 'role' trong Model UserRole
    role: RoleSimpleOut

    model_config = ConfigDict(from_attributes=True)


class UserInDBBase(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(UserInDBBase):
    user_roles: List[UserRoleOut] = []

