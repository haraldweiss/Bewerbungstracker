"""add_ai_provider_backup

Revision ID: b9d0e1f2g3h4
Revises: a8c9d0e1f2g3
Create Date: 2026-05-12 22:50:00.000000

Backup-/Fallback-Provider pro User. Wenn der primäre Provider nicht
erreichbar ist, routet der ai-provider-service Requests auf diesen Backup.
Nullable — Admin-User bekommen automatisch CLAUDE_API_KEY aus env als
Default (runtime via User.get_backup_config(), nicht in DB).
"""
from alembic import op
import sqlalchemy as sa


revision = 'b9d0e1f2g3h4'
down_revision = 'a8c9d0e1f2g3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('ai_provider_backup', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('ai_provider_backup_model', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('users', 'ai_provider_backup_model')
    op.drop_column('users', 'ai_provider_backup')
