"""widen rawjob.url to TEXT for long indeed tracker urls

Revision ID: 7c4d9f1a2b3e
Revises: e9fb6a021b20
Create Date: 2026-05-21 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c4d9f1a2b3e'
down_revision = 'e9fb6a021b20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite ignores VARCHAR length, so this is a no-op on SQLite but matters
    # for Postgres/MySQL migrations.
    with op.batch_alter_table('raw_jobs') as batch_op:
        batch_op.alter_column(
            'url',
            existing_type=sa.String(1024),
            type_=sa.Text(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('raw_jobs') as batch_op:
        batch_op.alter_column(
            'url',
            existing_type=sa.Text(),
            type_=sa.String(1024),
            existing_nullable=False,
        )
