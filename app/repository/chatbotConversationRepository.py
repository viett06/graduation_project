from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.chatbot_conversation import ChatbotConversation
from app.models.chatbot_message import ChatbotMessage


class ChatbotConversationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_conversation(self, user_id: int | None = None, title: str | None = None) -> ChatbotConversation:
        conversation = ChatbotConversation(user_id=user_id, title=title, is_active=True)
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def get_conversation(
            self,
            conversation_id: int,
            user_id: int | None = None,
    ) -> ChatbotConversation | None:
        stmt = select(ChatbotConversation).where(
            ChatbotConversation.id == conversation_id,
            ChatbotConversation.is_active == True,
        )
        if user_id is not None:
            stmt = stmt.where(ChatbotConversation.user_id == user_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def list_conversations_by_user(
            self,
            user_id: int,
            limit: int = 20,
            offset: int = 0,
    ) -> list[ChatbotConversation]:
        stmt = (
            select(ChatbotConversation)
            .where(
                ChatbotConversation.user_id == user_id,
                ChatbotConversation.is_active == True,
            )
            .order_by(desc(ChatbotConversation.updated_at))
            .offset(offset)
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def get_active_conversation_by_user(self, user_id: int) -> ChatbotConversation | None:
        stmt = (
            select(ChatbotConversation)
            .where(
                ChatbotConversation.user_id == user_id,
                ChatbotConversation.is_active == True,
            )
            .order_by(desc(ChatbotConversation.updated_at), desc(ChatbotConversation.id))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def add_message(
            self,
            conversation_id: int,
            role: str,
            content: str,
            intent: str | None = None,
            message_metadata: dict | None = None,
    ) -> ChatbotMessage:
        message = ChatbotMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            intent=intent,
            message_metadata=message_metadata,
        )
        self.session.add(message)
        self.session.flush()
        return message

    def get_recent_messages(self, conversation_id: int, limit: int = 10) -> list[ChatbotMessage]:
        stmt = (
            select(ChatbotMessage)
            .where(ChatbotMessage.conversation_id == conversation_id)
            .order_by(desc(ChatbotMessage.id))
            .limit(limit)
        )
        messages = self.session.execute(stmt).scalars().all()
        return list(reversed(messages))

    def update_summary(self, conversation: ChatbotConversation, summary: str | None):
        conversation.summary = summary
        self.session.add(conversation)
        self.session.flush()
        return conversation

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
