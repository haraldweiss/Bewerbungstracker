"""add User.job_type_blacklist

Revision ID: a9b8c7d6e5f4
Revises: f0778653c386
Create Date: 2026-06-05 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'a9b8c7d6e5f4'
down_revision = 'f0778653c386'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column(
            'job_type_blacklist',
            sa.Text(),
            nullable=False,
            server_default="'[]'",
        ),
    )


def downgrade():
    op.drop_column('users', 'job_type_blacklist')
