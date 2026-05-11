"""add_feature_model_overrides

Revision ID: a8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-05-11 10:00:00.000000

Per-User JSON-Overrides für Pro-Task-Modell-Konfiguration.
Nullable — fehlend = Fallback auf user.ai_provider/ai_provider_model.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a8c9d0e1f2g3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('feature_model_overrides', sa.Text, nullable=True))


def downgrade():
    op.drop_column('users', 'feature_model_overrides')
