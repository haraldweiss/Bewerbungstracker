"""add_match_suspicious_reasons

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-09 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('job_matches', sa.Column('suspicious_reasons', sa.Text, nullable=True))


def downgrade():
    op.drop_column('job_matches', 'suspicious_reasons')
