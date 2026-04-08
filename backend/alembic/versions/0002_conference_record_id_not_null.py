"""make conference_record_id not null

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-08
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("runs", "conference_record_id", nullable=False)


def downgrade() -> None:
    op.alter_column("runs", "conference_record_id", nullable=True)
