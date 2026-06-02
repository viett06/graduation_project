# Rate Limit Middleware

File code chính:

[ratelimiter.py](ratelimiter.py)

Middleware được đăng ký trong:

[app/main.py](../../../main.py)

```python
app.middleware("http")(rate_limit_middleware)
```

## 1. Mục tiêu

Rate limit dùng để giới hạn số request vào API theo từng loại client:

- `guest`: request không có token hoặc token không hợp lệ.
- `user`: request có access token hợp lệ.
- `admin`: request có access token hợp lệ và có role `admin`.

Mục tiêu:

- Chống spam request.
- Bảo vệ API public.
- Bảo vệ API đã login theo từng user.
- Cho admin quota cao hơn user thường.
- Không làm app chết nếu Redis lỗi.

## 2. Flow tổng quát

```text
Incoming HTTP request
  |
  |-- OPTIONS request? -> bypass
  |
  |-- Public path? -> bypass
  |
  v
Extract Authorization Bearer token
  |
  |-- No token / invalid token -> guest + identity by IP
  |
  |-- Valid access token -> identity by user_id
  |
  v
Resolve role scope
  |
  |-- roles contains admin -> admin policy
  |-- otherwise -> user policy
  |
  v
Apply sliding window limit
  |
  |-- exceeded -> 429
  |
  v
Apply token bucket limit
  |
  |-- exceeded -> 429
  |
  v
call_next(request)
```

## 3. Public Paths

Các path sau được bypass rate limit:

```python
PUBLIC_PATH_PREFIXES = (
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
)
```

Điều kiện bypass:

```text
path == prefix OR path starts with "{prefix}/"
```

Lưu ý hiện tại:

- Prefix `/` làm cho gần như mọi path đều match vì mọi path đều bắt đầu bằng `//`? Không, logic hiện tại check `path.startswith(f"{prefix}/")`; với prefix `/` thì thành `"//"`, nên các path như `/api/v1/...` không match.
- `path == "/"` vẫn bypass health check root.

## 4. Policy hiện tại

```python
RATE_LIMIT_POLICIES = {
    "guest": RateLimitPolicy(capacity=5, refill_rate=0.2, max_requests=20, window_time=60),
    "user": RateLimitPolicy(capacity=30, refill_rate=1.0, max_requests=120, window_time=60),
    "admin": RateLimitPolicy(capacity=100, refill_rate=5.0, max_requests=600, window_time=60),
}
```

| Scope | Token bucket capacity | Refill rate | Sliding window max | Window |
|---|---:|---:|---:|---:|
| `guest` | 5 requests burst | 0.2 req/sec | 20 requests | 60s |
| `user` | 30 requests burst | 1 req/sec | 120 requests | 60s |
| `admin` | 100 requests burst | 5 req/sec | 600 requests | 60s |

Ý nghĩa:

- `capacity`: số request burst tối đa tại một thời điểm.
- `refill_rate`: số token hồi lại mỗi giây.
- `max_requests`: giới hạn tổng request trong sliding window.
- `window_time`: thời gian cửa sổ sliding window, tính bằng giây.

## 5. Identity Resolution

### 5.1 Guest

Nếu không có token:

```text
scope = guest
identity = ip:{client_ip}
```

Nếu token sai hoặc không phải access token:

```text
scope = guest
identity = ip:{client_ip}
```

IP được lấy theo thứ tự:

1. `X-Forwarded-For`, lấy IP đầu tiên.
2. `X-Real-IP`.
3. `request.client.host`.
4. `"unknown"`.

### 5.2 Logged-in User

Nếu access token hợp lệ và có `user_id`:

```text
scope = user/admin
identity = user:{user_id}
```

Nếu access token hợp lệ nhưng không có `user_id`, fallback:

```text
scope = user/admin
identity = token:{sha256(token)}
```

## 6. Token Decode

Token được decode bằng:

```python
jwt.decode(
    token,
    settings.JWT_SECRET,
    algorithms=[settings.JWT_ALGORITHM],
)
```

Token chỉ được coi là hợp lệ cho rate limit nếu:

```python
payload.get("type") == "access"
```

Refresh token không được tính là user/admin. Nếu client gửi refresh token vào API thường, middleware xem như `guest`.

## 7. Role Scope

```python
if RoleEnum.ADMIN.value in roles:
    return "admin"
return "user"
```

Hiện tại chỉ role `admin` có quota riêng.

Các role khác như `manager`, `user` đều dùng policy `user`.

## 8. Redis Keys

Base key:

```text
rate_limit:{role_scope}:{identity}
```

Ví dụ:

```text
rate_limit:guest:ip:127.0.0.1
rate_limit:user:user:12
rate_limit:admin:user:1
```

Sliding window key:

```text
window:rate_limit:{role_scope}:{identity}
```

Token bucket key:

```text
bucket:rate_limit:{role_scope}:{identity}
```

## 9. Sliding Window Algorithm

Redis structure:

```text
ZSET
```

Flow:

```text
Remove entries older than window_start
  |
  v
Count current entries
  |
  |-- count >= max_requests -> limited
  |
  v
Add current request with score = now
  |
  v
Expire key after window_time + 1
```

Lua script:

```lua
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local count = redis.call('ZCARD', key)

if count >= max_requests then
    return 1
end

redis.call('ZADD', key, now, unique_id)
redis.call('EXPIRE', key, window_time + 1)
return 0
```

Trả về:

- `1`: bị giới hạn.
- `0`: cho qua.

## 10. Token Bucket Algorithm

Redis structure:

```text
HASH
```

Fields:

```text
tokens
last_refill
```

Flow:

```text
Read tokens and last_refill
  |
  v
Calculate elapsed time
  |
  v
Refill tokens = min(capacity, tokens + elapsed * rate)
  |
  |-- refilled >= 1 -> consume 1 token and allow
  |
  |-- refilled < 1 -> reject
```

TTL:

```python
ttl = math.ceil(capacity / rate) + 60
```

Ý nghĩa: Redis key tự hết hạn khi không còn traffic.

## 11. Response Khi Bị Limit

Status:

```http
429 Too Many Requests
```

Body:

```json
{
  "detail": "Too many requests. Please try again later."
}
```

Headers:

```http
Retry-After: 1
```

Frontend handling:

- Nếu nhận `429`, disable button hoặc debounce request.
- Hiển thị message ngắn: `Too many requests. Please try again later.`
- Có thể retry sau `Retry-After` giây.

## 12. Redis Failure Behavior

Nếu Redis lỗi trong middleware:

```python
except Exception as exc:
    print(f"Rate limit error: {exc}")
    limited = False
```

Nghĩa là:

- App không block request nếu Redis lỗi.
- Rate limit fail-open.
- Phù hợp để tránh downtime API.
- Không phù hợp nếu cần security strict tuyệt đối.

## 13. Test Cases

### 13.1 Guest Burst Limit

Không gửi token.

```http
GET /api/v1/banks
```

Expected:

- 5 request nhanh đầu tiên có thể qua theo token bucket.
- Request tiếp theo quá nhanh có thể trả `429`.

### 13.2 Guest Sliding Window

Không gửi token.

Gửi hơn 20 request trong 60 giây từ cùng IP.

Expected:

```http
429 Too Many Requests
```

### 13.3 User Limit

Gửi access token user thường.

```http
Authorization: Bearer {{user_access_token}}
```

Expected:

- Burst tối đa khoảng 30 request.
- Refill khoảng 1 request/giây.
- Tối đa 120 request/60 giây.

### 13.4 Admin Limit

Gửi access token admin.

```http
Authorization: Bearer {{admin_access_token}}
```

Expected:

- Burst tối đa khoảng 100 request.
- Refill khoảng 5 request/giây.
- Tối đa 600 request/60 giây.

### 13.5 Public Path Bypass

```http
GET /
GET /docs
GET /openapi.json
```

Expected:

- Không bị rate limit.

## 14. Manual Debug Redis

Liệt kê keys:

```bash
redis-cli keys 'rate_limit:*'
redis-cli keys 'window:rate_limit:*'
redis-cli keys 'bucket:rate_limit:*'
```

Xem sliding window:

```bash
redis-cli zcard 'window:rate_limit:guest:ip:127.0.0.1'
```

Xem token bucket:

```bash
redis-cli hgetall 'bucket:rate_limit:guest:ip:127.0.0.1'
```

Xóa key test:

```bash
redis-cli del 'window:rate_limit:guest:ip:127.0.0.1'
redis-cli del 'bucket:rate_limit:guest:ip:127.0.0.1'
```

## 15. Notes

- Middleware chạy cho mọi HTTP route sau khi app đăng ký middleware.
- WebSocket `/ws/rates` không đi qua HTTP middleware theo cùng cách request thường.
- Rate limit hiện chưa trả số quota còn lại như `X-RateLimit-Remaining`.
- Rate limit hiện chưa phân biệt từng endpoint, chỉ phân biệt scope + identity.
- Manager hiện đang dùng quota `user`, không có quota riêng.
- Refresh token không được tính là authenticated user trong middleware.

