"""rls"""

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

TABLES = None  # None = auto-detect all public tables
 
 
def _get_public_tables(connection):
    result = connection.execute(
        sa.text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            """
        )
    )
    return [row[0] for row in result]
 
 
def upgrade():
    connection = op.get_bind()
    tables = TABLES if TABLES else _get_public_tables(connection)
 
    for table in tables:
        connection.execute(
            sa.text(f'ALTER TABLE "public"."{table}" ENABLE ROW LEVEL SECURITY;')
        )
 
 
def downgrade():
    connection = op.get_bind()
    tables = TABLES if TABLES else _get_public_tables(connection)
 
    for table in tables:
        connection.execute(
            sa.text(f'ALTER TABLE "public"."{table}" DISABLE ROW LEVEL SECURITY;')
        )