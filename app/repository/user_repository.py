from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import UserRole, PermissionRole, Role
from app.models.user import User


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.session.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter(User.email == email).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:

        statement = select(User).offset(skip).limit(limit)
        return list(self.session.execute(statement).scalars().all())


#       SELECT
#     users.*,
#     user_roles.*,
#     roles.*,
#     permission_roles.*,
#     permissions.*
# FROM users
# -- 1. Join từ User sang bảng trung gian UserRole
# LEFT OUTER JOIN user_roles
#     ON users.id = user_roles.user_id
# -- 2. Join từ bảng trung gian sang bảng Role
# LEFT OUTER JOIN roles
#     ON user_roles.role_id = roles.id
# -- 3. Join từ Role sang bảng trung gian PermissionRole
# LEFT OUTER JOIN permission_roles
#     ON roles.id = permission_roles.role_id
# -- 4. Join từ bảng trung gian sang bảng Permission gốc
# LEFT OUTER JOIN permissions
#     ON permission_roles.permission_id = permissions.id
# WHERE users.email = 'email@example.com'
# LIMIT 1;



    def get_user_with_roles_and_permissions(self, email: str):
        return self.session.query(User).options(
            joinedload(User.user_roles)
            .joinedload(UserRole.role)
            .joinedload(Role.permission_roles)
            .joinedload(PermissionRole.permission)
        ).filter(User.email == email).first()


    def create(self, user_obj: User) -> User:
        self.session.add(user_obj)
        self.session.commit()
        self.session.refresh(user_obj)
        return user_obj

    def update(self, user_obj: User) -> Optional[User]:
        try:
            self.session.add(user_obj)
            self.session.commit()
            self.session.refresh(user_obj)
            return user_obj
        except Exception as e:
            self.session.rollback()
            print(f"Update error: {e}")
            return None

    def commit(self):
        self.session.commit()

    def refresh(self, user_obj: User):
        self.session.refresh(user_obj)