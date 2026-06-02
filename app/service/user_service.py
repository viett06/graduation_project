from typing import Optional, List, Dict, Any
from venv import create

from aiosmtplib import send
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.userSchema import UserCreate, UserUpdate
from app.core.security.auth_handler import AuthHandler
from app.repository.user_repository import UserRepository
import random
from fastapi import BackgroundTasks, HTTPException, status
from fastapi_mail import FastMail, MessageSchema, MessageType
from app.core.email_config import conf
from app.core.redis.redis_config import redis_client

class UserService:
    def __init__(self, session: Session, redis_client=redis_client):
        self.__userRepository = UserRepository(session=session)
        self.redis = redis_client

    async def create_user(self, user_data: UserCreate, background_tasks: BackgroundTasks) -> User:
        existing_user = self.__userRepository.get_by_email(user_data.email)
        hashed_password = AuthHandler.get_password_hash(user_data.password)

        if existing_user:
            if existing_user.is_active:
                raise ValueError("Email already registered")

            existing_user.first_name = user_data.first_name
            existing_user.last_name = user_data.last_name
            existing_user.hashed_password = hashed_password

            user = self.__userRepository.update(existing_user)
        else:
            user = User(
                email=user_data.email,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                hashed_password=hashed_password,
                is_active=False,
            )
            user = self.__userRepository.create(user)

        await self.send_otp(
            email=user.email,
            type_send="create_user",
            background_tasks=background_tasks,
        )

        return user

    # async def create_user(self, user_data: UserCreate, background_tasks: BackgroundTasks)-> User:
    #
    #     if not self.__userRepository.get_by_email(user_data.email):
    #         if self.__userRepository.get_by_email_is_unactive(user_data.email):
    #             raise HTTPException(status_code=400, detail="Email đã tồn tại dưới dạng chưa kích hoạt. Vui lòng kiểm tra email để kích hoạt tài khoản hoặc liên hệ hỗ trợ.")
    #         hashed_password = AuthHandler.get_password_hash(user_data.password)
    #
    #         # set role
    #
    #         user = User(
    #             email=user_data.email,
    #             first_name=user_data.first_name,
    #             last_name=user_data.last_name,
    #             hashed_password=hashed_password,
    #             is_active=False
    #         )
    #
    #         self.__userRepository.create(user)
    #
    #         await self.send_otp(email=user.email, type_send="create_user", background_tasks=background_tasks)
    #
    #         return user
    #
    #     elif self.__userRepository.get_by_email_is_unactive(user_data.email):
    #
    #         user = self.__userRepository.get_by_email_is_unactive(user_data.email)
    #
    #         hashed_password = AuthHandler.get_password_hash(user_data.password)
    #
    #         user.first_name = user_data.first_name
    #         user.last_name = user_data.last_name
    #         user.hashed_password = hashed_password
    #
    #         self.__userRepository.update(user)
    #
    #         await self.send_otp(email=user.email, type_send="create_user", background_tasks=background_tasks)
    #
    #         return user



    def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        user = self.__userRepository.get_by_id(user_id)
        if not user:
            return None

        update_data = user_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        self.__userRepository.commit()
        self.__userRepository.refresh(user)
        return user

    async def update_data_user_verify(self, user: User) -> Optional[User]:
        update_user = self.__userRepository.update(user)
        if not update_user:
            return None
        return update_user

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        # 1. Lấy user kèm theo tất cả Roles và Permissions
        user = self.__userRepository.get_user_with_roles_and_permissions(email)

        if not user or not AuthHandler.verify_password(password, user.hashed_password) or not user.is_active:
            return None

        # 2. Trích xuất danh sách tên Roles và Permissions từ object lồng nhau
        # Giả sử cấu trúc: user.user_roles -> list of UserRole -> role -> name
        roles = [ur.role.name for ur in user.user_roles]

        # Lấy permissions (tránh trùng lặp bằng set)
        permissions = set()
        for ur in user.user_roles:
            for pr in ur.role.permission_roles:
                permissions.add(pr.permission.name)

        # 3. Tạo Token với bộ data đã tổng hợp
        token_data = {"user_id": user.id, "email": user.email, "is_active": user.is_active, "is_superuser": user.is_superuser}

        access_token = AuthHandler.create_access_token(
            data=token_data,
            roles=roles,
            permissions=list(permissions)
        )
        refresh_token = AuthHandler.create_refresh_token(data=token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    def get_user(self, user_id: int) -> Optional[User]:
        return self.__userRepository.get_by_id(user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        return self.__userRepository.get_by_email(email)

    async def set_active_user(self, user: User) -> Optional[User]:
        user.is_active = True
        return user

    def list_users(self, page: int = 1, size: int = 10) -> List[User]:
        if page < 1: page = 1
        skip = (page - 1) * size
        return self.__userRepository.get_all(skip = skip, limit = size)

    async def send_otp(self, email: str, type_send: str,  background_tasks: BackgroundTasks):

        user = self.__userRepository.get_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        otp_code = str(random.randint(100000, 999999))

        prefix = "reset_otp"
        if type_send == "create_user":
            prefix = "create_user"

        elif type_send == "reset_password":
            prefix = "reset_otp"

        await self.redis.set(f"otp:{prefix}:{email}", otp_code, ex=300)

        html = f"""
                <p>Chào bạn,</p>
                <p>Mã OTP của bạn là: <b>{otp_code}</b></p>
                <p>Mã này sẽ hết hạn sau 5 phút.</p>
                """

        messages = MessageSchema(
            subject="Verification Code",
            recipients=[email],
            body=html,
            subtype=MessageType.html
        )

        fm = FastMail(conf)
        background_tasks.add_task(fm.send_message, messages)

        print(f"DEBUG: OTP {otp_code} sent to {email}")
        return True

    async def verify_otp(self, email: str, otp_code: str, type_send: str) -> bool:

        prefix = "reset_otp"
        if type_send == "create_user":
            prefix = "create_user"

        elif type_send == "reset_password":
            prefix = "reset_otp"

        stored_code = await self.redis.get(f"otp:{prefix}:{email}")
        if not stored_code or stored_code != otp_code:
            return False
        await self.redis.delete(f"otp:{prefix}:{email}")
        return True

    async def change_password(self, email: str, new_password: str) -> bool:
        user = self.__userRepository.get_by_email(email)
        if not user:
            return False

        hashed_pw = AuthHandler.get_password_hash(new_password)
        user.hashed_password = hashed_pw
        updated_user = self.__userRepository.update(user)
        return updated_user is not None








