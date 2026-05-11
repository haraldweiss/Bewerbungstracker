"""add_cover_letters

Revision ID: a7b8c9d0e1f2
Revises: a1b2c3d4e5f7
Create Date: 2026-05-11 09:00:00.000000

Neue Tabelle für den Anschreiben-Generator. Speichert Job-Posting + generiertes
Anschreiben (HTML mit data-confidence Attributen) + Analyse-JSON pro User.

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cover_letters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('application_id', sa.String(36), sa.ForeignKey('applications.id'), nullable=True),
        sa.Column('job_title', sa.String(255), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('job_description', sa.Text, nullable=False),
        sa.Column('cv_used', sa.String(255), nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('analysis_json', sa.Text, nullable=True),
        sa.Column('tone', sa.String(50), server_default='professional'),
        sa.Column('length', sa.String(50), server_default='medium'),
        sa.Column('focus', sa.String(50), server_default='balanced'),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('exported_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_cover_letters_user_id', 'cover_letters', ['user_id'])


def downgrade():
    op.drop_index('ix_cover_letters_user_id', table_name='cover_letters')
    op.drop_table('cover_letters')
