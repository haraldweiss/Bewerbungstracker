"""add_eval_attempts_to_job_matches

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-06-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'b0c1d2e3f4a5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_matches', sa.Column(
        'eval_attempts', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('job_matches', 'eval_attempts')
