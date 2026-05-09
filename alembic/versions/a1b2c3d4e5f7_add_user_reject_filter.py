"""add_user_reject_filter

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-05-09 14:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite hat kein einfaches ALTER mit DEFAULT auf bestehenden Tabellen —
    # wir nutzen server_default für den Initial-Backfill.
    op.add_column('users', sa.Column(
        'job_reject_filter_enabled',
        sa.Boolean(), nullable=False, server_default=sa.text('1'),
    ))
    op.add_column('users', sa.Column(
        'job_reject_window_days',
        sa.Integer(), nullable=False, server_default=sa.text('180'),
    ))


def downgrade():
    op.drop_column('users', 'job_reject_window_days')
    op.drop_column('users', 'job_reject_filter_enabled')
