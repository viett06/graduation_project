from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.role import Role

class RoleRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, role_id: int) -> Optional[Role]:
        return self.session.query(Role).filter(Role.id == role_id).first()

    def get_by_name(self, name: str) -> Optional[Role]:
        return self.session.query(Role).filter(Role.name == name).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Role]:
        return self.session.query(Role).offset(skip).limit(limit).all()

    def get_by_ids(self, role_ids: List[int]) -> List[Role]:
        return self.session.query(Role).filter(Role.id.in_(role_ids)).all()

    def create(self, role_obj: Role) -> Role:
        self.session.add(role_obj)
        self.session.commit()
        self.session.refresh(role_obj)
        return role_obj

    def delete(self, role_obj: Role) -> None:
        self.session.delete(role_obj)
        self.session.commit()

    def commit(self):
        self.session.commit()