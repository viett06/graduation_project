from enum import Enum

class MessageState(str, Enum):
    SENT = "sent"
    SEEN = "seen"