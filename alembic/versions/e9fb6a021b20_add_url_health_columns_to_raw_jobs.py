"""add_url_health_columns_to_raw_jobs

Revision ID: e9fb6a021b20
Revises: a3347f283f74
Create Date: 2026-05-19 17:18:53.210960

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9fb6a021b20'
down_revision = 'a3347f283f74'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('raw_jobs', sa.Column('url_last_checked_at', sa.DateTime(), nullable=True))
    op.add_column('raw_jobs', sa.Column('url_check_failures', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('raw_jobs', sa.Column('url_check_status', sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column('raw_jobs', 'url_check_status')
    op.drop_column('raw_jobs', 'url_check_failures')
    op.drop_column('raw_jobs', 'url_last_checked_at')
