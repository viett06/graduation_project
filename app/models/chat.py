from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import  datetime
from sqlalchemy.sql import func


class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    crated_at = Column(DateTime(timezone=True), server_default=func.now())

    # cố định ngay lần tạo đầu tiên do user tạo đến user nhận dữ liệu static
    sender_id = Column(Integer, ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False)

    sender = relationship("User",foreign_keys=[sender_id], back_populates="chats_sender",)
    receiver = relationship("User",foreign_keys=[receiver_id], back_populates="chats_receiver")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan",  passive_deletes=True)

