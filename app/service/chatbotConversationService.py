from sqlalchemy.orm import Session

from app.models.chatbot_conversation import ChatbotConversation
from app.repository.chatbotConversationRepository import ChatbotConversationRepository


class ChatbotConversationService:
    def __init__(self, session: Session):
        self.repository = ChatbotConversationRepository(session)

    def get_or_create_conversation(
            self,
            conversation_id: int | None = None,
            user_id: int | None = None,
            title: str | None = None,
    ) -> ChatbotConversation:
        if conversation_id:
            conversation = self.repository.get_conversation(conversation_id, user_id=user_id)
            if conversation:
                return conversation
            raise ValueError("Conversation not found.")

        return self.repository.create_conversation(user_id=user_id, title=title)

    def get_or_create_user_conversation(
            self,
            user_id: int,
            title: str | None = None,
    ) -> ChatbotConversation:
        if user_id is None:
            raise ValueError("Authenticated chatbot conversation requires user_id.")

        conversation = self.repository.get_active_conversation_by_user(user_id)
        if conversation:
            return conversation
        return self.repository.create_conversation(user_id=user_id, title=title)

    def list_user_conversations(
            self,
            user_id: int,
            page: int = 1,
            size: int = 20,
    ) -> list[ChatbotConversation]:
        if page < 1:
            page = 1
        if size < 1:
            size = 20
        offset = (page - 1) * size
        return self.repository.list_conversations_by_user(user_id=user_id, limit=size, offset=offset)

    def get_conversation_messages(
            self,
            conversation_id: int,
            user_id: int,
            limit: int = 50,
    ):
        conversation = self.repository.get_conversation(conversation_id, user_id=user_id)
        if not conversation:
            raise ValueError("Conversation not found.")
        return self.repository.get_recent_messages(conversation_id, limit=limit)

    def get_current_user_messages(self, user_id: int, limit: int = 20):
        conversation = self.repository.get_active_conversation_by_user(user_id)
        if not conversation:
            return []
        return self.repository.get_recent_messages(conversation.id, limit=limit)

    def build_context_messages(self, conversation_id: int, limit: int = 20) -> list[dict[str, str]]:
        messages = self.repository.get_recent_messages(conversation_id, limit=limit)
        return [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
            if message.role in {"user", "assistant"}
        ]

    def add_user_message(self, conversation_id: int, content: str):
        return self.repository.add_message(conversation_id, "user", content)

    def add_assistant_message(
            self,
            conversation_id: int,
            content: str,
            intent: str | None = None,
            message_metadata: dict | None = None,
    ):
        return self.repository.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            intent=intent,
            message_metadata=message_metadata,
        )

    def commit(self):
        self.repository.commit()

    def rollback(self):
        self.repository.rollback()
