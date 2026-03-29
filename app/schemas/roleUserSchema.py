from pydantic import BaseModel, ConfigDict

class RoleUserBase(BaseModel):
    user_id: int
    role_id:  int

    assigned_by: int

class RoleUserCreate(RoleUserBase):
    pass


class RoleUserInDBBase(RoleUserBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class RoleUserResponse(RoleUserInDBBase):
    pass





