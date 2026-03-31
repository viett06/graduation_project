from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import get_db
from app.core.security.seeder import seed_rbac

from app.api.enpoints import auth_controller, user_controller, bank_controller
from app.core.config import settings
from redis import asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager:
    - Chạy Startup logic: Seed dữ liệu RBAC vào DB.
    - Yield: App bắt đầu nhận request.
    - Chạy Shutdown logic.
    """
    # ── Startup ──
    db = next(get_db())
    try:
        print("Starting RBAC seeding...")
        seed_rbac(db)  # Sync Enum (Source of Truth) -> Database
        print("RBAC seeding completed.")
    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        db.close()

    app.state.redis = aioredis.from_url(
        "redis://localhost:6380",
        decode_responses=True
    )
    print("Redis connected.")

    yield 

    await app.state.redis.close()
    print("Redis disconnected.")


app = FastAPI(
    title="Auth & RBAC Management API",
    description="Hệ thống quản lý User và Phân quyền dựa trên Roles/Permissions",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    auth_controller.router, 
    prefix=f"{settings.API_V1_STR}/auth", 
    tags=["Auth"]
)

app.include_router(
    user_controller.router,
    prefix=f"{settings.API_V1_STR}/users",
    tags=["Users"]
)

app.include_router(
    bank_controller.router,
    prefix=f"{settings.API_V1_STR}/banks",
    tags=["Banks"]
)


@app.get("/", tags=["Health Check"])
def read_root():
    return {
        "status": "running",
        "message": "Auth & RBAC API is operational",
        "docs": "/docs"
    }