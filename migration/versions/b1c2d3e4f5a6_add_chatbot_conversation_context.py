"""add chatbot conversation context

Revision ID: b1c2d3e4f5a6
Revises: a718c69f6fd0
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a718c69f6fd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chatbot_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chatbot_conversations_id'), 'chatbot_conversations', ['id'], unique=False)

    op.create_table(
        'chatbot_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('intent', sa.String(length=100), nullable=True),
        sa.Column('message_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['chatbot_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chatbot_messages_conversation_id'), 'chatbot_messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_chatbot_messages_id'), 'chatbot_messages', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chatbot_messages_id'), table_name='chatbot_messages')
    op.drop_index(op.f('ix_chatbot_messages_conversation_id'), table_name='chatbot_messages')
    op.drop_table('chatbot_messages')
    op.drop_index(op.f('ix_chatbot_conversations_id'), table_name='chatbot_conversations')
    op.drop_table('chatbot_conversations')
