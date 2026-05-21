from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class ChatbotMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    intent: str | None = None
    message_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatbotConversationResponse(BaseModel):
    id: int
    user_id: int | None = None
    title: str | None = None
    summary: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatbotPromptRequest(BaseModel):
    prompt: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_common_prompt_keys(cls, data):
        if isinstance(data, dict):
            for key in ("prompt", "message", "content", "text"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    data["prompt"] = value.strip()
                    return data
        return data


class ChatbotPromptResponse(BaseModel):
    conversation_id: int | None = None
    answer: str
