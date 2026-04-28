"""Add user settings_json + cv_data_json columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('settings_json', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('cv_data_json', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'cv_data_json')
    op.drop_column('users', 'settings_json')
