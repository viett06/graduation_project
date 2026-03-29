"""
AuthHandler - JWT creation & verification
──────────────────────────────────────────
Thay đổi chính so với bản cũ:
  1. create_access_token nhận thêm roles + permissions → embed vào claims
  2. Sửa comment sai ("Create Refresh Token" → "Create Access Token")
  3. Token chứa đủ data → get_current_user không cần query DB
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthHandler:
    SECRET_KEY  = settings.JWT_SECRET
    ALGORITHM   = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRE_DAYS   = settings.REFRESH_TOKEN_EXPIRE_DAYS

    # ── Password ──────────────────────────────────────────────

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return pwd_context.hash(password)

    # ── Token creation ────────────────────────────────────────

    @classmethod
    def create_access_token(
        cls,
        data: Dict[str, Any],
        roles: List[str] = [],
        permissions: List[str] = [],
    ) -> str:
        """
        Tạo Access Token có embed roles + permissions.

        Tại sao embed vào token thay vì query DB mỗi request?
        - Stateless: không cần DB round-trip để authorize
        - Performance: 1 query lúc login, sau đó đọc từ RAM
        - Scale: nhiều instance server vẫn verify được cùng 1 token

        Trade-off: nếu role bị thu hồi → phải đợi token hết hạn
        → Giải quyết bằng: giảm ACCESS_TOKEN_EXPIRE_MINUTES hoặc Redis blacklist
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({
            "exp":         expire,
            "type":        "access",
            "roles":       roles,        # ["admin", "manager"]
            "permissions": permissions,  # ["user:read", "user:delete"]
        })
        return jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def create_refresh_token(cls, data: Dict[str, Any]) -> str:
        """
        Tạo Refresh Token — KHÔNG chứa roles/permissions.
        Lúc refresh sẽ query DB lại để lấy roles/permissions mới nhất.
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    # ── Token decoding ─────────────────────────────────────────

    @classmethod
    def decode_token(cls, token: str) -> Dict[str, Any]:
        """Decode và validate token. Raise 401 nếu expired hoặc invalid."""
        try:
            return jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )