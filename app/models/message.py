from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from app.db.base import Base
from sqlalchemy.sql import func

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    content = Column(String)
    state_message = Column(String)
    type_message = Column(String)
    media_file_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender_id = Column(Integer)
    recipient_id = Column(Integer)
    chat_id = Column(Integer, ForeignKey("chats.id", onupdate="CASCADE", ondelete="CASCADE"))

    chat = relationship("Chat", back_populates="messages")
