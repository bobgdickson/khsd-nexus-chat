"""create chatkit tables

Revision ID: 202411200001
Revises:
Create Date: 2024-11-20 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "202411200001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatkit_threads",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_chatkit_threads_created_at",
        "chatkit_threads",
        ["created_at"],
    )

    op.create_table(
        "chatkit_thread_items",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("thread_id", sa.String(length=255), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["chatkit_threads.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_chatkit_thread_items_thread_id",
        "chatkit_thread_items",
        ["thread_id"],
    )
    op.create_index(
        "ix_chatkit_thread_items_created_at",
        "chatkit_thread_items",
        ["created_at"],
    )

    op.create_table(
        "chatkit_attachments",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("upload_url", sa.String(length=1024), nullable=True),
        sa.Column("file_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("chatkit_attachments")
    op.drop_index("ix_chatkit_thread_items_created_at", table_name="chatkit_thread_items")
    op.drop_index("ix_chatkit_thread_items_thread_id", table_name="chatkit_thread_items")
    op.drop_table("chatkit_thread_items")
    op.drop_index("ix_chatkit_threads_created_at", table_name="chatkit_threads")
    op.drop_table("chatkit_threads")
