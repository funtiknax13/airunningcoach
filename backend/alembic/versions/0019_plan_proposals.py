"""Chat plan proposals: draft plan stored on the chat message, confirmed via button

Revision ID: 0019_plan_proposals
Revises: 0018_plan_zones
Create Date: 2026-10-27

Только добавляющая nullable-колонка — старые сообщения чата продолжают работать без изменений.
"""
import sqlalchemy as sa
from alembic import op

revision = '0019_plan_proposals'
down_revision = '0018_plan_zones'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('plan_draft', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'plan_draft')
