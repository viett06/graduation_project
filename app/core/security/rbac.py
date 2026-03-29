"""
RBAC Enums - Source of Truth cho toàn bộ hệ thống quyền
─────────────────────────────────────────────────────────
Java mindset: @RolesAllowed, @PermitAll trong annotation
Python mindset: Enum làm source of truth → sync vào DB lúc startup → check từ JWT
"""

from enum import Enum

class PermissionEnum(str, Enum):
    """
    Định nghĩa TẤT CẢ permissions của hệ thống.
    str, Enum cho phép so sánh trực tiếp với string: PermissionEnum.USER_READ == "user:read" → True
    """
    # User permissions
    USER_CREATE = "user:create"
    USER_READ   = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Role permissions
    ROLE_CREATE = "role:create"
    ROLE_READ   = "role:read"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"

    # Permission management
    PERMISSION_CREATE = "permission:create"
    PERMISSION_READ   = "permission:read"
    PERMISSION_UPDATE = "permission:update"
    PERMISSION_DELETE = "permission:delete"


class RoleEnum(str, Enum):
    """
    Định nghĩa TẤT CẢ roles của hệ thống.
    """
    ADMIN   = "admin"
    MANAGER = "manager"
    USER    = "user"


# Map mặc định role → permissions
# Dùng để: seed DB lúc startup, KHÔNG dùng để check runtime
DEFAULT_ROLE_PERMISSIONS: dict[RoleEnum, list[str]] = {
    RoleEnum.ADMIN: [p.value for p in PermissionEnum],  # tất cả quyền
    RoleEnum.MANAGER: [
        PermissionEnum.USER_READ.value,
        PermissionEnum.USER_UPDATE.value,
        PermissionEnum.ROLE_READ.value,
    ],
    RoleEnum.USER: [
        PermissionEnum.USER_READ.value,
    ],
}