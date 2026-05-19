"""add_learned_email_patterns

Revision ID: a3347f283f74
Revises: 2e8256d612cd
Create Date: 2026-05-19 14:39:11.521192

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3347f283f74'
down_revision = '2e8256d612cd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'learned_email_patterns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('platform', sa.String(32), nullable=False),
        sa.Column('pattern_json', sa.Text(), nullable=False),
        sa.Column('sample_count', sa.Integer(), nullable=False),
        sa.Column('hit_rate', sa.Float(), nullable=False),
        sa.Column('trained_at', sa.DateTime(), nullable=False),
        sa.Column('trained_by_user_id', sa.String(36),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('rolled_back_at', sa.DateTime(), nullable=True),
        sa.Column('rolled_back_by_user_id', sa.String(36),
                  sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_index(
        'ix_learned_email_patterns_platform',
        'learned_email_patterns', ['platform']
    )
    op.create_index(
        'ux_lep_one_active_per_platform',
        'learned_email_patterns', ['platform'],
        unique=True,
        sqlite_where=sa.text('is_active = 1'),
        postgresql_where=sa.text('is_active = TRUE'),
    )


def downgrade():
    op.drop_index('ux_lep_one_active_per_platform', 'learned_email_patterns')
    op.drop_index('ix_learned_email_patterns_platform', 'learned_email_patterns')
    op.drop_table('learned_email_patterns')
