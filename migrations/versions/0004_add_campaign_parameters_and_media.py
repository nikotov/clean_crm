"""add campaign parameter mapping and header media fields

Revision ID: 0004
Revises: 0003_campaigns_module
Create Date: 2026-07-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003_campaigns_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "campaigns" in inspector.get_table_names():
        campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}

        if "parameter_mapping_json" not in campaign_columns:
            op.add_column(
                "campaigns",
                sa.Column(
                    "parameter_mapping_json",
                    sa.JSON(),
                    nullable=True,
                    comment="Mapping of placeholder numbers to customer field names, e.g. {'1': 'name', '2': 'cellphone'}",
                ),
            )

        if "header_media_url" not in campaign_columns:
            op.add_column(
                "campaigns",
                sa.Column(
                    "header_media_url",
                    sa.String(length=1024),
                    nullable=True,
                    comment="Public URL of the media to use in the template header for this campaign",
                ),
            )

        if "header_media_id" not in campaign_columns:
            op.add_column(
                "campaigns",
                sa.Column(
                    "header_media_id",
                    sa.String(length=128),
                    nullable=True,
                    comment="YCloud media ID (if uploaded) to use in the template header for this campaign",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "campaigns" in inspector.get_table_names():
        campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}

        if "header_media_id" in campaign_columns:
            op.drop_column("campaigns", "header_media_id")
        if "header_media_url" in campaign_columns:
            op.drop_column("campaigns", "header_media_url")
        if "parameter_mapping_json" in campaign_columns:
            op.drop_column("campaigns", "parameter_mapping_json")