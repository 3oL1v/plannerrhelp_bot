from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_today_slots_hide"
down_revision = "0001_mvp_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("bot_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("user_settings", sa.Column("bot_summary_message_id", sa.Integer(), nullable=True))
    op.add_column("user_settings", sa.Column("bot_events_message_id", sa.Integer(), nullable=True))
    op.add_column("user_settings", sa.Column("bot_tasks_message_id", sa.Integer(), nullable=True))
    op.add_column("user_settings", sa.Column("today_completed_hidden_before", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "today_completed_hidden_before")
    op.drop_column("user_settings", "bot_tasks_message_id")
    op.drop_column("user_settings", "bot_events_message_id")
    op.drop_column("user_settings", "bot_summary_message_id")
    op.drop_column("user_settings", "bot_chat_id")
