"""
Auth Controller
────────────────
Thay đổi chính so với bản cũ:
  - login: query roles + permissions → embed vào access token
  - refresh: query lại DB → đảm bảo token mới có roles mới nhất
  - register: giữ nguyên, assign default role "user"
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, session

from app.api.deps import get_db
from app.core.security.auth_handler import AuthHandler
from app.schemas.token import RefreshToken, Token
from app.schemas.userSchema import UserCreate, UserResponse
from app.service.role_service import RoleService
from app.service.user_service import UserService
from app.core.security.rbac import RoleEnum



router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db),
):
    user_service = UserService(session)
    result = user_service.authenticate(form_data.username, form_data.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(**result)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: RefreshToken,
    session: Session = Depends(get_db),
):
    """
    Refresh access token.

    Query lại DB ở đây vì:
    - User có thể đã được gán/thu hồi role trong thời gian token sống
    - Refresh token tồn tại lâu hơn → cần cập nhật claims mới nhất
    """
    payload = AuthHandler.decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = payload.get("user_id")
    user_service = UserService(session)
    role_service  = RoleService(session)

    user = user_service.get_user(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Query lại DB để lấy roles/permissions mới nhất
    claims = role_service.get_user_roles_and_permissions(user.id)

    new_access_token = AuthHandler.create_access_token(
        data={
            "user_id":      user.id,
            "email":        user.email,
            "is_superuser": user.is_superuser,
            "is_active":    user.is_active,
        },
        roles=claims["roles"],
        permissions=claims["permissions"],
    )

    return Token(
        access_token=new_access_token,
        refresh_token=body.refresh_token,  # giữ nguyên refresh token cũ
        token_type="bearer",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: Session = Depends(get_db),
):
    """Đăng ký user mới với default role 'user'."""
    user_service = UserService(session)
    role_service  = RoleService(session)

    try:
        user = user_service.create_user(user_data)

        default_role = role_service.get_role_by_name(RoleEnum.USER.value)
        if default_role:
            role_service.assign_role_to_user(user.id, default_role.id, user.id)

        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(email: str, request: Request, background_tasks: BackgroundTasks, session: Session = Depends(get_db) ):

    redis_client = request.app.state.redis

    user_service = UserService(session, redis_client)

    return await user_service.send_otp(email, background_tasks)

@router.post("/verify-reset-password")
async def verify_reset_password(email: str, otp_code: str, newpassword: str, request: Request, session: Session = Depends(get_db),):

    user_service = UserService(session, request.app.state.redis)

    is_valid = user_service.verify_otp(email, otp_code)

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="OTP code not valid"
        )

    success = await user_service.change_password(email, newpassword)

    if not success:
        raise HTTPException(status_code=404, detail="user not found")

    return {"status": "success", "message": "successful change password"}













