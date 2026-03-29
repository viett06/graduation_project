from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    user_id: int
    type: str
    exp: Optional[int] = None

class RefreshToken(BaseModel):
    refresh_token: str

