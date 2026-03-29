"""
RBAC Seeder - Sync Enum → Database lúc startup
────────────────────────────────────────────────
Đảm bảo Enum (source of truth) và DB luôn đồng bộ.
Gọi 1 lần trong app startup event.

Tương đương Java: data.sql hoặc Liquibase/Flyway migration cho seed data
"""

from sqlalchemy.orm import Session

from app.core.security.rbac import DEFAULT_ROLE_PERMISSIONS, PermissionEnum, RoleEnum
from app.models.permission import Permission
from app.models.permissionRole import PermissionRole
from app.models.role import Role


def seed_rbac(db: Session) -> None:
    """
    Tạo permissions, roles và gán permission mặc định vào DB nếu chưa có.
    Idempotent: chạy nhiều lần không bị lỗi duplicate.
    """
    _seed_permissions(db)
    _seed_roles(db)
    _seed_role_permissions(db)
    print("[RBAC] Seed completed.")


def _seed_permissions(db: Session) -> None:
    """Tạo Permission row cho từng PermissionEnum nếu chưa tồn tại."""
    for perm in PermissionEnum:
        exists = db.query(Permission).filter_by(name=perm.value).first()
        if not exists:
            db.add(Permission(name=perm.value))
    db.commit()


def _seed_roles(db: Session) -> None:
    """Tạo Role row cho từng RoleEnum nếu chưa tồn tại."""
    for role in RoleEnum:
        exists = db.query(Role).filter_by(name=role.value).first()
        if not exists:
            db.add(Role(name=role.value))
    db.commit()


def _seed_role_permissions(db: Session) -> None:
    """Gán permissions mặc định cho từng role theo DEFAULT_ROLE_PERMISSIONS."""
    for role_enum, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.query(Role).filter_by(name=role_enum.value).first()
        if not role:
            continue

        for perm_name in perm_names:
            perm = db.query(Permission).filter_by(name=perm_name).first()
            if not perm:
                continue

            exists = db.query(PermissionRole).filter_by(
                role_id=role.id,
                permission_id=perm.id,
            ).first()

            if not exists:
                db.add(PermissionRole(role_id=role.id, permission_id=perm.id))

    db.commit()