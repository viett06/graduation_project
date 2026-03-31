from pydantic import BaseModel, ConfigDict
from datetime import datetime

class MessageBase(BaseModel):
    content: str
    sender_id: int
    receiver_id: int
    type_message: str
    chat_id: int

class CreateMessageBase(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: int
    created_at: datetime
    state_message: str
    media_file_path: str

    model_config = ConfigDict(from_attributes=True)