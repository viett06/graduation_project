from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.userSchema import UserCreate, UserUpdate
from app.core.security.auth_handler import AuthHandler
from app.repository.user_repository import UserRepository
import random
from fastapi import BackgroundTasks, HTTPException, status
from fastapi_mail import FastMail, MessageSchema, MessageType
from redis import asyncio as aioredis
from app.core.email_config import conf

class UserService:
    def __init__(self, session: Session, redis_client=None):
        self.__userRepository = UserRepository(session=session)
        self.__redis = redis_client

    def create_user(self, user_data: UserCreate) -> User:

        if self.__userRepository.get_by_email(user_data.email):
            raise ValueError("Email already registered")

        hashed_password = AuthHandler.get_password_hash(user_data.password)

        # set role

        user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            hashed_password=hashed_password
        )

        # 4. Gọi Repository để lưu
        return self.__userRepository.create(user)

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

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        # 1. Lấy user kèm theo tất cả Roles và Permissions
        user = self.__userRepository.get_user_with_roles_and_permissions(email)

        if not user or not AuthHandler.verify_password(password, user.hashed_password):
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

    def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.__userRepository.get_all(skip, limit)

    async def send_otp(self, email: str, background_tasks: BackgroundTasks):
        otp_code = str(random.randint(100000,999999))

        await self.__redis.set(f"otp:reset:{email}", otp_code, ex=300)

        html = f"""
                <p>Chào bạn,</p>
                <p>Mã OTP của bạn là: <b>{otp_code}</b></p>
                <p>Mã này sẽ hết hạn sau 5 phút. Vui lòng không chia sẻ cho bất kỳ ai.</p>
                <p>Đây là email tự động từ hệ thống. Vui lòng không phản hồi lại email này.</p>
                """

        messages = MessageSchema(
            subject="Your verification code",
            recipients=[email],
            body= html,
            subtype=MessageType.html,
            reply_to=["noreply@gmail.com"]
        )

        fm = FastMail(conf)

        background_tasks.add_task(fm.send_message, messages)

        # return {"status": "success", "message": "OTP has been sent to your email"}
        print('send otp code successfully')
        return None

    async def verify_otp(self, otp_code: str, email: str) -> bool:
        stored_code = await self.__redis.get(f"otp:reset:{email}")

        if otp_code is None:
            return False

        if stored_code != otp_code:
            return False

        await self.__redis.delete(f"otp:reset:{email}")

        return True

    async def change_password(self, email: str, new_password: str) -> bool:

        user = self.__userRepository.get_by_email(email)

        if not user:
            return False

        change_password_hash = AuthHandler.get_password_hash(new_password)

        user.hashed_password = change_password_hash

        user = self.__userRepository.update(user)

        if user:
            return True
        else:
            return False









