"""add customer cellphone column

Revision ID: 0002_customers_cellphone
Revises: 0001_initial_schema
Create Date: 2026-06-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_customers_cellphone"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    customer_columns = {column["name"] for column in inspector.get_columns("customers")}

    if "cellphone" not in customer_columns:
        op.add_column("customers", sa.Column("cellphone", sa.String(length=40), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    customer_columns = {column["name"] for column in inspector.get_columns("customers")}

    if "cellphone" in customer_columns:
        op.drop_column("customers", "cellphone")