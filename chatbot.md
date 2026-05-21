# Chatbot System

Tài liệu này mô tả ngắn gọn cách chatbot hoạt động trong hệ thống.

## Chatbot dùng để làm gì?

Chatbot hỗ trợ người dùng trong các câu hỏi liên quan đến lãi suất và gửi tiết kiệm, ví dụ:

- Tra cứu lãi suất của một ngân hàng.
- So sánh lãi suất giữa nhiều ngân hàng.
- Tính tiền lãi dự kiến khi gửi tiết kiệm.
- So sánh số tiền lãi giữa hai ngân hàng.
- Gợi ý hoặc lập kế hoạch gửi tiết kiệm.

Nếu câu hỏi nằm ngoài phạm vi này, chatbot sẽ trả lời:

```text
câu hỏi của bạn sẽ được cập nhật sau.
```

## Cách người dùng sử dụng

Người dùng có thể hỏi trực tiếp bằng ngôn ngữ tự nhiên:

```text
lãi suất MSB kỳ hạn 12 tháng là bao nhiêu?
```

```text
so sánh lãi suất MSB và PVB với số tiền 100 triệu trong 12 tháng
```

```text
tôi có 200 triệu, nên gửi tiết kiệm thế nào trong 1 năm?
```

Nếu câu hỏi thiếu thông tin quan trọng, chatbot sẽ hỏi lại thay vì tự đoán. Ví dụ, nếu người dùng muốn tính tiền lãi nhưng chưa nhập số tiền gửi, chatbot sẽ yêu cầu bổ sung số tiền.

## Flow tổng quan

Luồng xử lý hiện tại:

```text
Người dùng gửi câu hỏi
  -> Hệ thống xác định ý định và thông tin cần dùng
  -> Backend kiểm tra và chuẩn hóa dữ liệu
  -> Backend gọi service phù hợp
  -> Kết quả được rút gọn
  -> Chatbot viết lại câu trả lời dễ hiểu cho người dùng
  -> Nếu người dùng đã đăng nhập, hệ thống lưu lại hội thoại
```

Model không tự quyết định dữ liệu nào là đúng. Việc lấy lãi suất, tính toán, so sánh và tạo kế hoạch đều do backend xử lý.

## Người dùng đã đăng nhập

Endpoint:

```http
POST /api/v1/chatbot
```

Endpoint này cần JWT access token.

Request:

```json
{
  "prompt": "so sánh lãi suất MSB và PVB kỳ hạn 12 tháng"
}
```

Response:

```json
{
  "conversation_id": 1,
  "answer": "..."
}
```

Với người dùng đã đăng nhập, hệ thống lưu lại hội thoại. Mỗi user có một conversation riêng, giúp chatbot có thể hiểu được câu hỏi tiếp theo trong cùng ngữ cảnh.

Ví dụ:

```text
User: so sánh số tiền lãi giữa MSB và PVB
Bot: Bạn muốn gửi bao nhiêu tiền và trong kỳ hạn bao lâu?
User: 100 triệu trong 12 tháng
Bot: ...
```

Ở câu trả lời thứ hai, chatbot vẫn hiểu MSB và PVB là hai ngân hàng đang được nhắc tới.

## Khách chưa đăng nhập

Endpoint:

```http
POST /api/v1/chatbot/public
```

Endpoint này không cần token.

Request:

```json
{
  "prompt": "lãi suất ngân hàng nào cao nhất hiện nay"
}
```

Response:

```json
{
  "conversation_id": null,
  "answer": "..."
}
```

Với guest, hệ thống không tạo conversation và không lưu lịch sử chat. Mỗi câu hỏi được xử lý độc lập.

## Lấy lịch sử chat

Endpoint:

```http
GET /api/v1/chatbot/messages?limit=20
```

Endpoint này cần token và trả về các tin nhắn gần nhất trong conversation của user hiện tại.

## Các nhóm xử lý chính

Chatbot hiện hỗ trợ các nhóm intent sau:

- `get_rates`: tra cứu lãi suất.
- `calculate_deposit_interest`: tính tiền lãi gửi tiết kiệm.
- `compare_bank_interest`: so sánh tiền lãi giữa các ngân hàng.
- `create_saving_plan`: lập kế hoạch gửi tiết kiệm.
- `out_of_scope`: câu hỏi ngoài phạm vi hỗ trợ.

Sau khi xác định được intent, backend sẽ gọi service tương ứng để lấy dữ liệu hoặc tính toán.

## Một vài nguyên tắc xử lý

- Chatbot chỉ trả lời trong phạm vi tài chính ngân hàng đang hỗ trợ.
- Nếu thiếu dữ liệu bắt buộc, chatbot hỏi lại người dùng.
- Nếu dữ liệu lãi suất quá nhiều, backend chỉ gửi phần cần thiết để chatbot viết câu trả lời.
- Guest không có context hội thoại.
- User đã đăng nhập có context từ các tin nhắn gần nhất.

## Các file chính

```text
app/agent/chatbot_router.py
app/agent/chatbot_service.py
app/models/chatbot_conversation.py
app/models/chatbot_message.py
app/schemas/chatbotConversationSchema.py
app/repository/chatbotConversationRepository.py
app/service/chatbotConversationService.py
app/service/bankService.py
app/repository/bank_repository.py
app/service/interestRateService.py
app/repository/interestRateRepository.py
```

## Ghi chú

- Authenticated chatbot dùng `POST /api/v1/chatbot`.
- Public chatbot dùng `POST /api/v1/chatbot/public`.
- Message history chỉ có với user đã đăng nhập.
- Khi cần debug hội thoại, kiểm tra conversation, messages và metadata được lưu trong database.
