"""
Security Dependencies
──────────────────────
get_current_user: đọc từ JWT claims → KHÔNG query DB mỗi request
get_current_active_user: wrapper kiểm tra is_active
get_current_superuser: wrapper kiểm tra is_superuser

Java mindset: SecurityContextHolder.getContext().getAuthentication() — thread-local
Python mindset: Depends chain — FastAPI inject tự động vào từng request
"""

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security.auth_handler import AuthHandler
from app.core.security.oauth2_scheme import oauth2_scheme


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """
    Decode JWT → trả về user context từ claims.

    KHÔNG query DB ở đây vì:
    - Roles + permissions đã được embed vào JWT lúc login
    - Mỗi request query DB = N+1 problem, không scale
    - JWT là stateless by design

    Nếu cần data mới nhất (vd: user bị ban) → dùng Redis blacklist token
    hoặc giảm ACCESS_TOKEN_EXPIRE_MINUTES
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = AuthHandler.decode_token(token)  # raise 401 nếu expired/invalid

    # Validate token type — tránh dùng refresh token như access token
    if payload.get("type") != "access":
        raise credentials_exception

    user_id: Optional[int] = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    # Lấy trực tiếp từ JWT claims — không cần query DB
    return {
        "user_id":      user_id,
        "email":        payload.get("email"),
        "roles":        payload.get("roles", []),        # ["admin", "manager"]
        "permissions":  payload.get("permissions", []),  # ["user:read", "user:delete"]
        "is_superuser": payload.get("is_superuser", False),
        "is_active":    payload.get("is_active", True),
    }


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Kiểm tra user còn active không.
    Dùng cho các endpoint cần login nhưng không cần quyền đặc biệt.
    """
    if not current_user.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    return current_user


async def get_current_superuser(
    current_user: Dict[str, Any] = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Chỉ cho phép superuser.
    Dùng cho các endpoint hệ thống cực kỳ nhạy cảm.
    """
    if not current_user.get("is_superuser"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user