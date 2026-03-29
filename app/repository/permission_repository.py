from typing import Optional, List, Type
from sqlalchemy.orm import Session
from app.models.permission import Permission
from app.schemas.permissionSchema import PermissionCreate

class PermissionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, permission_id: int) -> Optional[Permission]:
        return self.session.query(Permission).filter(Permission.id == permission_id).first()

    def get_by_name(self, name: str) -> Optional[Permission]:
        return self.session.query(Permission).filter(Permission.name == name).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Permission]:

        return self.session.query(Permission).offset(skip).limit(limit).all()

    def create(self, permission_obj: Permission) -> Permission:
        self.session.add(permission_obj)
        self.session.commit()
        self.session.refresh(permission_obj)
        return permission_obj

    def update(self) -> None:
        self.session.commit()

    def delete(self, permission_obj: Permission) -> None:
        self.session.delete(permission_obj)
        self.session.commit()