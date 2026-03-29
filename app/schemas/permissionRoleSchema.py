from pydantic import BaseModel, ConfigDict

class PermissionRoleBase(BaseModel):
    permission_id: int
    role_id: int

class PermissionRoleCreate(PermissionRoleBase):
    pass

class PermissionInDBBase(PermissionRoleBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class PermissionRoleResponse(PermissionInDBBase):
    pass