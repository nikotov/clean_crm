"""make customer email nullable

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "customers",
        "email",
        nullable=True,
        existing_type=sa.String(length=255),
        existing_unique=True,
    )


def downgrade() -> None:
    op.alter_column(
        "customers",
        "email",
        nullable=False,
        existing_type=sa.String(length=255),
        existing_unique=True,
    )