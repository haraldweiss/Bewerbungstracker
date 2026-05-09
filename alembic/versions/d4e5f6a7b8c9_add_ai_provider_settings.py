"""add_ai_provider_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('ai_provider', sa.String(50), nullable=False, server_default='claude'))
    op.add_column('users', sa.Column('ai_provider_model', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('users', 'ai_provider_model')
    op.drop_column('users', 'ai_provider')
