"""
RBAC Guards - Dependency functions để bảo vệ endpoints
────────────────────────────────────────────────────────
Java mindset: @PreAuthorize("hasRole('ADMIN')") — AOP proxy intercept
Python mindset: Depends(require_role(...)) — FastAPI DI pipeline

TẠI SAO KHÔNG DÙNG DECORATOR?
  Decorator thông thường (@require_role) KHÔNG hoạt động với FastAPI vì:
  - FastAPI resolve Depends() bằng cách scan signature của route function trực tiếp
  - Depends() bên trong @wraps wrapper bị ignore hoàn toàn
  - Kết quả: current_user luôn là None hoặc raise error

CÁCH ĐÚNG: trả về dependency function → FastAPI tự gọi + inject
"""

from typing import Any, Dict
from fastapi import Depends, HTTPException, status

from app.core.security.rbac import PermissionEnum, RoleEnum
from app.core.security.dependencies import get_current_user


# ─────────────────────────────────────────────
# Helper nội bộ
# ─────────────────────────────────────────────

def _check_permissions(current_user: Dict[str, Any], permissions: tuple[PermissionEnum, ...]) -> None:
    """Kiểm tra user có đủ permissions không. Raise 403 nếu thiếu."""
    if current_user.get("is_superuser"):
        return  # superuser bypass tất cả

    user_perms: set[str] = set(current_user.get("permissions", []))
    missing = [p.value for p in permissions if p.value not in user_perms]

    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permissions: {', '.join(missing)}",
        )


def _check_roles(current_user: Dict[str, Any], roles: tuple[RoleEnum, ...]) -> None:
    """Kiểm tra user có ít nhất 1 trong các roles không. Raise 403 nếu không có."""
    if current_user.get("is_superuser"):
        return  # superuser bypass tất cả

    user_roles: list[str] = current_user.get("roles", [])

    if not any(r.value in user_roles for r in roles):
        allowed = ", ".join(r.value for r in roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required one of roles: [{allowed}]",
        )


# ─────────────────────────────────────────────
# Public guards — dùng với Depends()
# ─────────────────────────────────────────────

def require_permissions(*permissions: PermissionEnum):
    """
    Trả về dependency function kiểm tra permissions.

    Dùng:
        @router.delete("/users/{id}")
        async def delete_user(
            id: int,
            user = Depends(require_permissions(PermissionEnum.USER_DELETE))
        ):

    Tương đương Java:
        @PreAuthorize("hasAuthority('user:delete')")
    """
    async def dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        _check_permissions(current_user, permissions)
        return current_user

    return dependency


def require_roles(*roles: RoleEnum):
    """
    Trả về dependency function kiểm tra roles.

    Dùng:
        @router.get("/admin/dashboard")
        async def dashboard(
            user = Depends(require_roles(RoleEnum.ADMIN))
        ):

    Tương đương Java:
        @PreAuthorize("hasRole('ADMIN')")
    """
    async def dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        _check_roles(current_user, roles)
        return current_user

    return dependency


def require_roles_and_permissions(*roles: RoleEnum, permissions: tuple[PermissionEnum, ...] = ()):
    """
    Kết hợp: phải có role VÀ đủ permissions.

    Dùng:
        @router.post("/users/{id}/promote")
        async def promote_user(
            id: int,
            user = Depends(require_roles_and_permissions(
                RoleEnum.ADMIN,
                permissions=(PermissionEnum.USER_UPDATE,)
            ))
        ):
    """
    async def dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        _check_roles(current_user, roles)
        if permissions:
            _check_permissions(current_user, permissions)
        return current_user

    return dependency