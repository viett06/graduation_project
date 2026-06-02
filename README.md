# OAuth2 Auth & Saving Plan API

Backend FastAPI cho hệ thống:

- Đăng ký, xác thực OTP, đăng nhập OAuth2 password flow.
- JWT access token / refresh token.
- RBAC theo role và permission.
- Quản lý user, ngân hàng, lãi suất, audit log.
- Tính toán và lập kế hoạch gửi tiết kiệm.
- Chatbot tư vấn ngân hàng/lãi suất/kế hoạch tiết kiệm.
- Scheduler cập nhật dữ liệu lãi suất.
- Redis cho OTP, rate limit và context phụ trợ.

Base API mặc định:

```text
/api/v1
```

Swagger:

```text
/docs
```

Health check:

```text
GET /
```

## 1. Kiến trúc tổng quan

```text
Client / Frontend
  |
  | HTTP / WebSocket
  v
FastAPI app
  |
  |-- Auth Controller
  |-- User Controller
  |-- Bank Controller
  |-- Rate Controller
  |-- Saving Plan Controller
  |-- Chatbot Router
  |-- Crawler / Scheduler
  |
  v
Service layer
  |
  |-- UserService
  |-- RoleService
  |-- BankService
  |-- InterestRateService
  |-- SavingPlanService
  |-- Chatbot services
  |
  v
Repository layer
  |
  |-- SQLAlchemy / DB
  |-- Redis
```

Router registration nằm ở [app/main.py](app/main.py):

| Module | Prefix |
|---|---|
| Auth | `/api/v1/auth` |
| Users | `/api/v1/users` |
| Banks | `/api/v1/banks` |
| Rates | `/api/v1/rates` |
| Audit logs | `/api/v1/audit-logs` |
| Chatbot | `/api/v1/chatbot` |
| Crawler | `/api/v1/crawler` |
| Saving plan | `/api/v1/saving-plan` |

## 2. Startup Flow

Khi app start, lifespan trong [app/main.py](app/main.py) chạy theo thứ tự:

```text
Start app
  |
  |-- Seed RBAC roles/permissions
  |-- Connect Redis
  |-- Start APScheduler
  v
App ready
```

Khi app shutdown:

```text
Shutdown app
  |
  |-- Close Redis
  |-- Stop APScheduler
```

## 3. Auth Flow

### 3.1 Register User

Endpoint:

```http
POST /api/v1/auth/register/user
```

Flow hiện tại:

```text
User nhập thông tin đăng ký
  |
  v
Backend tạo user với is_active = false
  |
  v
Backend gửi OTP qua email
  |
  v
User chờ verify OTP
```

Request:

```json
{
  "email": "user@example.com",
  "first_name": "Le",
  "last_name": "Nguyen",
  "password": "password123"
}
```

Response: `UserResponse`.

### 3.2 Verify User OTP

Endpoint:

```http
POST /api/v1/auth/verify-user?email=user@example.com&otp_code=123456
```

Flow:

```text
User nhập OTP
  |
  v
Backend kiểm tra Redis key otp:create_user:{email}
  |
  |-- OTP đúng: set user.is_active = true
  |-- OTP sai/hết hạn: trả 400
```

Sau khi active, user mới đăng nhập được.

### 3.3 Login

Endpoint:

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded
```

Body:

```text
username=user@example.com
password=password123
```

Flow:

```text
Email/password
  |
  v
Check user exists + password đúng + is_active = true
  |
  v
Query roles + permissions
  |
  v
Create access token + refresh token
```

Response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

Frontend lưu `access_token` và gửi header:

```http
Authorization: Bearer {{access_token}}
```

### 3.4 Refresh Token

Endpoint:

```http
POST /api/v1/auth/refresh
```

Request:

```json
{
  "refresh_token": "{{refresh_token}}"
}
```

Flow:

```text
Decode refresh token
  |
  |-- type != refresh: reject
  |
  v
Query user từ DB
  |
  |-- user inactive/not found: reject
  |
  v
Query roles/permissions mới nhất
  |
  v
Create access token mới
```

Refresh token hiện tại được giữ nguyên cho tới khi hết hạn.

### 3.5 Forgot Password

Gửi OTP reset password:

```http
POST /api/v1/auth/forgot-password?email=user@example.com
```

Verify OTP và đổi mật khẩu:

```http
POST /api/v1/auth/verify-reset-password?email=user@example.com&otp_code=123456&newpassword=newpass123
```

## 4. RBAC Flow

Token chứa:

```json
{
  "user_id": 1,
  "email": "user@example.com",
  "is_active": true,
  "is_superuser": false,
  "type": "access",
  "roles": ["admin"],
  "permissions": ["user:update"]
}
```

Guard chính:

- `get_current_active_user`: yêu cầu login và user active trong token.
- `require_roles(...)`: yêu cầu một trong các role.
- `require_permissions(...)`: yêu cầu permission.

Role mặc định:

- `/auth/register/user`: role `user`.
- `/auth/register/manager`: role `manager`, cần admin/manager.
- `/auth/register/admin`: role `admin`, cần admin/manager.

## 5. User API Flow

Prefix:

```text
/api/v1/users
```

| Method | Path | Mục đích | Auth |
|---|---|---|---|
| GET | `/me` | Lấy user hiện tại | Login |
| GET | `` | Danh sách users | Admin/Manager |
| PUT | `/{user_id}` | Cập nhật user | Permission `USER_UPDATE` |
| DELETE | `/{user_id}` | Xóa user | Permission `USER_DELETE` |

Frontend thường gọi:

```text
Login -> GET /api/v1/users/me -> lưu thông tin user hiện tại
```

## 6. Bank API Flow

Prefix:

```text
/api/v1/banks
```

| Method | Path | Mục đích |
|---|---|---|
| POST | `` | Tạo ngân hàng, cần admin/manager |
| GET | `` | Danh sách ngân hàng |
| GET | `/search` | Tìm theo name/code |
| GET | `/{bank_id}` | Chi tiết ngân hàng |
| PUT | `/{bank_id}` | Cập nhật ngân hàng, cần admin/manager |
| DELETE | `/{bank_id}` | Xóa mềm ngân hàng, cần admin/manager |
| GET | `/bank_rates` | Danh sách bank + lãi suất theo kỳ hạn/số tiền |
| GET | `/bank_rates/{bank_id}` | Bank kèm danh sách lãi suất |
| POST | `/calculate` | Tính lãi một ngân hàng/kỳ hạn |
| POST | `/compare-calculate` | So sánh nhiều phương án tính lãi |

Flow quản trị ngân hàng:

```text
Admin/Manager login
  |
  v
Create bank
  |
  v
Create interest rates
  |
  v
Frontend/user có thể search, compare, calculate
```

## 7. Interest Rate API Flow

Prefix thực tế:

```text
/api/v1/rates/interest-rates
```

Do `rate_controller.py` có router prefix nội bộ `/interest-rates`.

| Method | Path | Mục đích | Auth |
|---|---|---|---|
| POST | `/` | Tạo một lãi suất | Admin/Manager |
| POST | `/bulk` | Tạo nhiều lãi suất theo ma trận | Admin/Manager |
| PUT | `/{interest_rate_id}` | Cập nhật lãi suất | Admin/Manager |
| DELETE | `/{interest_rate_id}` | Xóa lãi suất | Admin/Manager |

Lãi suất được dùng bởi:

- `/banks/bank_rates`
- `/banks/calculate`
- `/saving-plan/optimize`
- `/saving-plan/plan-by-term`
- Chatbot tư vấn lãi suất.

## 8. Saving Plan Flow

Prefix:

```text
/api/v1/saving-plan
```

Chi tiết test case cho frontend nằm ở:

[test/saving_plan_api_test_cases.md](test/saving_plan_api_test_cases.md)

### 8.1 Optimize Plan

Endpoint:

```http
POST /api/v1/saving-plan/optimize
Authorization: Bearer {{access_token}}
```

Request:

```json
{
  "name": "Ke hoach tiet kiem 12 thang",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106000000,
  "prefer_rate": "ONLINE",
  "codes": ["VCB", "TCB"],
  "notes": "Plan from frontend"
}
```

Flow:

```text
User nhập số tiền + thời gian + mục tiêu
  |
  v
Backend lấy lãi suất ngân hàng theo duration_month
  |
  v
DPOptimizer chạy DP + beam search
  |
  v
Trả best_plan + top_plans
```

Lưu ý hiện tại:

- Không còn gửi thêm hàng tháng.
- Không còn lịch gửi thêm.
- Không còn rút tiền.
- Không còn chọn thuật toán từ frontend.
- Backend luôn dùng `dp`.

Response chính:

```json
{
  "plan_id": null,
  "final_amount": 106500000,
  "achieved_interest": 6500000,
  "is_goal_met": true,
  "plan_details": {},
  "top_plans": [],
  "algorithm_used": "dp",
  "probability_success": null
}
```

### 8.2 Plan By Term

Endpoint:

```http
POST /api/v1/saving-plan/plan-by-term
Authorization: Bearer {{access_token}}
```

Request:

```json
{
  "total_amount": 100000000,
  "term_month": 12,
  "channel": "ONLINE"
}
```

Flow:

```text
User chọn kỳ hạn
  |
  v
Backend query DB tìm lãi suất cao nhất đúng kỳ hạn
  |
  v
Gửi toàn bộ số tiền vào ngân hàng/kênh có lãi suất cao nhất
  |
  v
Trả final_amount + interest + timeline
```

Endpoint này không optimize.

### 8.3 Save Plan

Endpoint:

```http
POST /api/v1/saving-plan/{user_id}/save
Authorization: Bearer {{access_token}}
```

Request:

```json
{
  "name": "Gui tiet kiem 12 thang",
  "duration_month": 12,
  "total_amount": 100000000,
  "goal_amount": 106500000,
  "notes": "Selected by user",
  "plan_data": {
    "strategy": "fixed_term_highest_rate",
    "summary": {},
    "steps": []
  }
}
```

Lưu ý: backend hiện lấy `user_id` từ token, không lấy từ path.

### 8.4 History, Detail, Delete

| Method | Path | Mục đích |
|---|---|---|
| GET | `/history/{user_id}` | Lịch sử active plans |
| GET | `/{user_id}` | Danh sách active plans |
| GET | `/{user_id}/{plan_id}` | Chi tiết plan |
| DELETE | `/{user_id}/{plan_id}` | Xóa mềm plan |

Flow frontend khuyến nghị:

```text
Login
  |
  v
Optimize hoặc Plan By Term
  |
  v
User chọn plan
  |
  v
Save plan
  |
  v
History / Detail / Delete
```

## 9. Saving Algorithm Summary

Thuật toán chính nằm ở:

[app/service/algorithm/dp_algorithm.py](app/service/algorithm/dp_algorithm.py)

Mục tiêu:

- Tìm phương án gửi tiết kiệm tốt nhất trong nhiều ngân hàng/kỳ hạn.
- Có thể chia tiền thành nhiều sổ.
- Có thể giữ cash hưởng lãi không kỳ hạn.
- Có thể mở sổ mới sau khi sổ cũ đáo hạn.
- So sánh với benchmark gửi một lần.

State DP:

```python
State = (cash, tuple(active_books))
```

Flow thuật toán:

```text
Initial amount
  |
  v
Build bank profiles from DB rates
  |
  v
Initialize DP state
  |
  v
For each month:
  - close matured books
  - hold cash option
  - open new book options
  - merge duplicate states
  - beam prune
  |
  v
Final close all books
  |
  v
Rank and format top plans
```

Các action có thể xuất hiện trong timeline:

| Action | Ý nghĩa |
|---|---|
| `initial` | Số tiền ban đầu |
| `open_book` | Mở sổ tiết kiệm |
| `mature` | Sổ đáo hạn |
| `hold_cash` | Giữ tiền mặt |
| `kkh_interest` | Lãi không kỳ hạn |
| `early_close` | Tất toán cuối kỳ khi sổ chưa đáo hạn |
| `transfer_fee` | Phí chuyển khoản nếu có |
| `transfer_wait` | Mất lãi do thời gian chờ nếu có |
| `final_balance` | Số dư cuối kỳ |

## 10. Chatbot Flow

Prefix:

```text
/api/v1/chatbot
```

| Method | Path | Mục đích | Auth |
|---|---|---|---|
| POST | `` | Chat có login, lưu context user | Login |
| POST | `/public` | Chat public, không lưu context user | Public |
| POST | `/stream` | Streaming chat có login | Login |
| POST | `/public/stream` | Streaming chat public | Public |
| GET | `/messages` | Lấy lịch sử message user hiện tại | Login |

Flow:

```text
User nhập prompt
  |
  v
Intent detection / tool selection
  |
  |-- search bank/rates
  |-- calculate interest
  |-- create saving plan
  |-- fallback LLM answer
  |
  v
Return answer + structured payload
```

## 11. Audit Log Flow

Prefix:

```text
/api/v1/audit-logs
```

Endpoint:

```http
GET /api/v1/audit-logs/
```

Audit log được dùng cho các thao tác quản trị như cập nhật/xóa ngân hàng hoặc lãi suất.

## 12. Crawler, Scheduler, WebSocket

### Crawler

Prefix:

```text
/api/v1/crawler
```

Dùng để trigger hoặc quản lý crawl dữ liệu tùy controller hiện tại.

### Scheduler

Scheduler start khi app startup:

```text
start_scheduler()
```

Mục tiêu: cập nhật dữ liệu lãi suất theo lịch.

### WebSocket Rates

Endpoint:

```text
ws://{{host}}/ws/rates
```

Dùng để giữ kết nối realtime cho dữ liệu lãi suất nếu frontend cần.

## 13. Frontend Integration Order

Thứ tự tích hợp khuyến nghị:

1. Auth register / verify / login.
2. Lưu `access_token` và gọi `/users/me`.
3. Hiển thị danh sách ngân hàng: `GET /banks`.
4. Hiển thị lãi suất theo kỳ hạn/số tiền: `GET /banks/bank_rates`.
5. Tích hợp `POST /saving-plan/plan-by-term`.
6. Tích hợp `POST /saving-plan/optimize`.
7. Tích hợp save/history/detail/delete saving plan.
8. Tích hợp chatbot nếu cần.
9. Tích hợp admin bank/rate CRUD nếu làm dashboard quản trị.

## 14. Manual Test Checklist

### Auth

```text
POST /auth/register/user
POST /auth/verify-user
POST /auth/login
POST /auth/refresh
POST /auth/forgot-password
POST /auth/verify-reset-password
```

### Bank / Rate

```text
GET  /banks
GET  /banks/search
GET  /banks/bank_rates
POST /banks/calculate
POST /banks/compare-calculate
POST /rates/interest-rates/
POST /rates/interest-rates/bulk
```

### Saving Plan

```text
POST   /saving-plan/optimize
POST   /saving-plan/plan-by-term
POST   /saving-plan/{user_id}/save
GET    /saving-plan/history/{user_id}
GET    /saving-plan/{user_id}/{plan_id}
DELETE /saving-plan/{user_id}/{plan_id}
```

## 15. Known Notes

- Saving plan hiện chỉ dùng DP, không cho frontend chọn thuật toán.
- Saving plan hiện không nhận gửi thêm hàng tháng, lịch gửi thêm hoặc lịch rút tiền.
- `POST /saving-plan/{user_id}/save` lấy user từ token, path `user_id` chỉ còn ý nghĩa routing.
- Một số route history/detail/delete saving plan hiện chưa gắn auth guard trong controller.
- Refresh token hiện chưa rotate/revoke; access token được cấp mới, refresh token cũ được giữ nguyên.
- Register user tạo user inactive trước, verify OTP mới active.

