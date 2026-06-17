"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "customers" not in inspector.get_table_names():
        op.create_table(
            "customers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("birthdate", sa.DateTime(timezone=False), nullable=True),
            sa.Column("age", sa.Integer(), nullable=True),
            sa.Column("city", sa.String(length=255), nullable=True),
        )

    if "tags" not in inspector.get_table_names():
        op.create_table(
            "tags",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=120), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
        )

    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=255), nullable=False, unique=True),
            sa.Column("hash_password", sa.String(length=255), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_login", sa.DateTime(timezone=False), nullable=True),
        )

    if "notes" not in inspector.get_table_names():
        op.create_table(
            "notes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        )

    if "tag_maps" not in inspector.get_table_names():
        op.create_table(
            "tag_maps",
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("customer_id", "tag_id", name="uq_tag_maps_customer_tag"),
        )


def downgrade() -> None:
    op.drop_table("tag_maps")
    op.drop_table("notes")
    op.drop_table("users")
    op.drop_table("tags")
    op.drop_table("customers")