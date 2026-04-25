"""Extend applications: legacy fields + soft delete

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-25

Bringt das Application-Schema auf den Stand der Legacy-DB (bewerbungen.db.bak),
damit eine 1:1-Migration der 43 alten Bewerbungen ohne Datenverlust möglich ist.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy-Felder
    op.add_column('applications', sa.Column('salary', sa.String(length=100), nullable=True))
    op.add_column('applications', sa.Column('location', sa.String(length=200), nullable=True))
    op.add_column('applications', sa.Column('contact_email', sa.String(length=255), nullable=True))
    op.add_column('applications', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('applications', sa.Column('link', sa.Text(), nullable=True))
    op.add_column('applications', sa.Column('notes', sa.Text(), nullable=True))

    # Soft-Delete (default False, nullable=False für stabile Filter-Queries)
    op.add_column(
        'applications',
        sa.Column('deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('applications', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index(
        op.f('ix_applications_deleted'), 'applications', ['deleted'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_applications_deleted'), table_name='applications')
    op.drop_column('applications', 'deleted_at')
    op.drop_column('applications', 'deleted')
    op.drop_column('applications', 'notes')
    op.drop_column('applications', 'link')
    op.drop_column('applications', 'source')
    op.drop_column('applications', 'contact_email')
    op.drop_column('applications', 'location')
    op.drop_column('applications', 'salary')
