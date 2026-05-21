"""add platform_profiles table

Revision ID: b3e4f5a6c7d8
Revises: 7c4d9f1a2b3e
Create Date: 2026-05-21 16:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = 'b3e4f5a6c7d8'
down_revision = '7c4d9f1a2b3e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'platform_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(120), nullable=False),
        sa.Column('domain', sa.String(120), nullable=False),
        sa.Column('subject_must_contain', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('ai_schema_hint', sa.Text(), nullable=True),
        sa.Column('digest_threshold', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('url_pattern_override', sa.Text(), nullable=True),
        sa.Column('from_whitelist_override', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_user_id', sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.UniqueConstraint('slug', name='uq_platform_profiles_slug'),
    )


def downgrade():
    op.drop_table('platform_profiles')
