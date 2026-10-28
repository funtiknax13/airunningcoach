"""Plan preference note: free-text memory from chat (replaces regex extraction)

Revision ID: 0020_plan_pref_note
Revises: 0019_plan_proposals
Create Date: 2026-10-28

Только добавляющие nullable-колонки — существующие строки plan_preferences не трогаем.
"""
import sqlalchemy as sa
from alembic import op

revision = '0020_plan_pref_note'
down_revision = '0019_plan_proposals'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('plan_preferences', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('plan_preferences', sa.Column('note_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('plan_preferences', 'note_expires_at')
    op.drop_column('plan_preferences', 'note')
