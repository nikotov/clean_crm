"""add campaigns module tables

Revision ID: 0003_campaigns_module
Revises: 0002_customers_cellphone
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_campaigns_module"
down_revision = "0002_customers_cellphone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "campaign_templates" not in tables:
        op.create_table(
            "campaign_templates",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=120), nullable=False, unique=True),
            sa.Column("ycloud_template_name", sa.String(length=120), nullable=False),
            sa.Column("language_code", sa.String(length=32), nullable=False),
            sa.Column("category", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("components", sa.JSON(), nullable=False),
            sa.Column("approval_note", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(timezone=False), nullable=True),
        )

    if "campaigns" not in tables:
        op.create_table(
            "campaigns",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("template_id", sa.Integer(), sa.ForeignKey("campaign_templates.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("sender_phone_number", sa.String(length=40), nullable=False),
            sa.Column("audience_rule", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("scheduled_for", sa.DateTime(timezone=False), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("launched_at", sa.DateTime(timezone=False), nullable=True),
        )

    if "campaign_recipients" not in tables:
        op.create_table(
            "campaign_recipients",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("recipient_phone", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("ycloud_message_id", sa.String(length=128), nullable=True),
            sa.Column("external_id", sa.String(length=128), nullable=True, unique=True),
            sa.Column("failure_reason", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=False), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=False), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("campaign_recipients")
    op.drop_table("campaigns")
    op.drop_table("campaign_templates")
