from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

from app.agent import chatbot_router
from app.api.deps import get_db
from app.core.security.seeder import seed_rbac
from app.api.enpoints import auth_controller, user_controller, bank_controller, rate_controller, auditLog_controller, crawler
from app.core.config import settings
from app.core.middleware.ratelimiter import rate_limit_middleware
from app.core.socket.websocket import manager
from app.core.APSscheduler.scheduler import start_scheduler, stop_scheduler
from app.core.redis.redis_config import init_redis, close_redis

load_dotenv()

# --- Gộp tất cả logic vào MỘT lifespan duy nhất ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Khởi tạo DB Seeding (Startup)
    db = next(get_db())
    try:
        print("Starting RBAC seeding...")
        seed_rbac(db)
        print("RBAC seeding completed.")
    except Exception as e:
        print(f"Error during seeding: {e}")
    finally:
        db.close()

    # 2. Kết nối Redis
    await init_redis()
    print("Redis connected.")

    # 3. Chạy Scheduler
    start_scheduler()
    print("Scheduler started.")

    yield # --- App chạy ở đây ---

    # 4. Cleanup (Shutdown)
    await close_redis()
    stop_scheduler()
    print("System cleanup: Redis & Scheduler stopped.")

# --- Khởi tạo FastAPI MỘT LẦN DUY NHẤT ---
app = FastAPI(
    title="Auth & RBAC Management API",
    description="Hệ thống quản lý User và Phân quyền dựa trên Roles/Permissions",
    version="1.0.0",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(rate_limit_middleware)

# --- Routes ---
app.include_router(auth_controller.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(user_controller.router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(bank_controller.router, prefix=f"{settings.API_V1_STR}/banks", tags=["Banks"])
app.include_router(rate_controller.router, prefix=f"{settings.API_V1_STR}/rates", tags=["Rates"])
app.include_router(auditLog_controller.router, prefix=f"{settings.API_V1_STR}/audit-logs", tags=["Audits"])

app.include_router(chatbot_router.router, prefix=f"{settings.API_V1_STR}/chatbot", tags=["Chatbot"])
app.include_router(crawler.router,prefix=f"{settings.API_V1_STR}/crawler", tags=["Crawler"])

app.include_router(crawler.router,prefix=f"{settings.API_V1_STR}/saving-plan", tags=["Saving Plan"])



# --- WebSockets ---
@app.websocket("/ws/rates")
async def websocket_rates(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Nhận message từ client hoặc chỉ giữ kết nối
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/", tags=["Health Check"])
def read_root():
    return {
        "status": "running",
        "message": "Auth & RBAC API is operational",
        "docs": "/docs"
    }