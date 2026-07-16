"""add campaign parameter mapping and header media fields

Revision ID: 0004_add_campaign_parameters_and_media
Revises: 0003_campaigns_module
Create Date: 2026-07-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_add_campaign_parameters_and_media"
down_revision = "0003_campaigns_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Only alter the campaigns table if it exists and the columns are missing
    if "campaigns" in inspector.get_table_names():
        campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}

        # Add parameter_mapping_json (store as JSON)
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

        # Add header_media_url
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

        # Add header_media_id
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

        # Optionally, add an index on header_media_id for faster lookups
        # op.create_index("ix_campaigns_header_media_id", "campaigns", ["header_media_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "campaigns" in inspector.get_table_names():
        campaign_columns = {column["name"] for column in inspector.get_columns("campaigns")}

        # Remove columns in reverse order
        if "header_media_id" in campaign_columns:
            op.drop_column("campaigns", "header_media_id")
        if "header_media_url" in campaign_columns:
            op.drop_column("campaigns", "header_media_url")
        if "parameter_mapping_json" in campaign_columns:
            op.drop_column("campaigns", "parameter_mapping_json")