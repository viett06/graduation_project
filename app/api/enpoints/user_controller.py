"""
User Router - Ví dụ dùng RBAC guards đúng cách với FastAPI
────────────────────────────────────────────────────────────
So sánh với Java Spring:

  Java:                               Python FastAPI:
  ─────────────────────────────────   ──────────────────────────────────────────
  @PreAuthorize("hasRole('ADMIN')")   Depends(require_roles(RoleEnum.ADMIN))
  @PreAuthorize("hasAuth('u:del')")   Depends(require_permissions(PermissionEnum.USER_DELETE))
  @Secured({"ADMIN","MANAGER"})       Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER))
  SecurityContextHolder.getContext()  current_user dict được inject qua Depends
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security.rbac import PermissionEnum, RoleEnum
from app.core.security.guards import require_permissions, require_roles
from app.core.security.dependencies import get_current_active_user
from app.schemas.userSchema import UserResponse, UserUpdate
from app.service.user_service import UserService

# router = APIRouter(prefix="/users", tags=["users"])
router = APIRouter()

# ── Endpoint công khai với user đang login ────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(
    # Chỉ cần login, không cần quyền đặc biệt
    current_user: Dict[str, Any] = Depends(get_current_active_user),
):
    """Lấy thông tin user hiện tại."""
    return current_user


# ── Endpoint cần permission cụ thể ───────────────────────────

@router.get("", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(get_db),
    # Chỉ user có quyền USER_READ mới vào được
    _: Dict = Depends(require_permissions(PermissionEnum.USER_READ)),
):
    """Danh sách users — cần permission user:read."""
    return UserService(session).list_users(skip, limit)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    session: Session = Depends(get_db),
    current_user: Dict = Depends(require_permissions(PermissionEnum.USER_UPDATE)),
):
    """Cập nhật user — cần permission user:update."""
    return UserService(session).update_user(user_id, body)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    session: Session = Depends(get_db),
    # Cần CẢ role admin VÀ permission user:delete
    _: Dict = Depends(require_permissions(PermissionEnum.USER_DELETE)),
):
    """Xóa user — cần permission user:delete."""
    UserService(session).delete_user(user_id)


# ── Endpoint chỉ dành cho role cụ thể ────────────────────────

@router.get("/admin/overview")
async def admin_overview(
    session: Session = Depends(get_db),
    # Chỉ ADMIN hoặc MANAGER được vào
    current_user: Dict = Depends(require_roles(RoleEnum.ADMIN, RoleEnum.MANAGER)),
):
    """Dashboard admin — chỉ ADMIN hoặc MANAGER."""
    return {"total_users": UserService(session).count_users()}