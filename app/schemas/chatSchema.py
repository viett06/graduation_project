
from pydantic import BaseModel
from datetime import datetime

class ChatBase(BaseModel):
    id: int
    name: str
    unread_count: int
    last_message: str
    last_message_time: datetime
    is_recipient_online: bool
    sender_id: int
    receiver_id: int