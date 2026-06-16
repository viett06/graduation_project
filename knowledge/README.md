# Knowledge Base

Thư mục này chứa tài liệu dạng markdown cho RAG.

## Vai trò trong chatbot

Chatbot dùng hai loại nguồn dữ liệu:

- Structured tools: lãi suất, tính lãi, so sánh ngân hàng, lập kế hoạch tiết kiệm.
- Knowledge base: FAQ, thuật ngữ, chính sách chung, hướng dẫn sử dụng app.

Không dùng RAG để thay thế dữ liệu lãi suất hoặc phép tính. RAG chỉ bổ sung kiến thức dạng tài liệu.

## Format tài liệu

Mỗi file nên có frontmatter:

```md
---
title: "FAQ gửi tiết kiệm"
category: "faq"
bank_code:
---
```

Nội dung chia theo heading:

```md
# Rút trước hạn

Nội dung giải thích...
```

Retriever sẽ chia mỗi heading thành một hoặc nhiều chunk và trả về `content` kèm `source`.

## Mở rộng sau này

`KnowledgeBaseService` hiện dùng local markdown retriever để dễ học và không cần hạ tầng mới. Khi cần production hơn, thay phần retriever bên trong service bằng pgvector, Qdrant hoặc embeddings API. Agent chỉ gọi `search(query, top_k)`, nên flow chatbot không cần đổi.
