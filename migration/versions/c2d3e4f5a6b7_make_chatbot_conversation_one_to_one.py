"""make chatbot conversation one to one

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-21 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id
                       ORDER BY updated_at DESC NULLS LAST, id DESC
                   ) AS rn
            FROM chatbot_conversations
            WHERE user_id IS NOT NULL
        )
        UPDATE chatbot_messages AS m
        SET conversation_id = keep.id
        FROM ranked AS duplicate
        JOIN ranked AS keep
          ON keep.rn = 1
         AND duplicate.rn > 1
         AND keep.id <> duplicate.id
        JOIN chatbot_conversations AS duplicate_conversation
          ON duplicate_conversation.id = duplicate.id
        JOIN chatbot_conversations AS keep_conversation
          ON keep_conversation.id = keep.id
         AND keep_conversation.user_id = duplicate_conversation.user_id
        WHERE m.conversation_id = duplicate.id
    """)

    op.execute("""
        DELETE FROM chatbot_conversations AS c
        USING (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id
                       ORDER BY updated_at DESC NULLS LAST, id DESC
                   ) AS rn
            FROM chatbot_conversations
            WHERE user_id IS NOT NULL
        ) AS ranked
        WHERE c.id = ranked.id
          AND ranked.rn > 1
    """)

    op.execute("DELETE FROM chatbot_conversations WHERE user_id IS NULL")
    op.alter_column('chatbot_conversations', 'user_id', nullable=False)
    op.create_unique_constraint(
        'uq_chatbot_conversations_user_id',
        'chatbot_conversations',
        ['user_id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_chatbot_conversations_user_id',
        'chatbot_conversations',
        type_='unique',
    )
    op.alter_column('chatbot_conversations', 'user_id', nullable=True)
