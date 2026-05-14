"""adaptive_learning_fields_and_tables

Revision ID: 2e8256d612cd
Revises: 0e97494ca404
Create Date: 2026-05-14 13:24:38.253138

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2e8256d612cd'
down_revision = '0e97494ca404'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JobMatch: feedback fields
    with op.batch_alter_table('job_matches') as batch:
        batch.add_column(sa.Column('feedback_reasons', sa.Text(), nullable=True))
        batch.add_column(sa.Column('feedback_text', sa.Text(), nullable=True))

    # User: learn settings
    with op.batch_alter_table('users') as batch:
        batch.add_column(sa.Column('job_learn_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('job_learn_min_samples', sa.Integer(), nullable=False, server_default='3'))
        batch.add_column(sa.Column('job_learn_weight_pct', sa.Integer(), nullable=False, server_default='30'))

    # JobEmbedding table
    op.create_table(
        'job_embeddings',
        sa.Column('raw_job_id', sa.Integer(), nullable=False),
        sa.Column('vector', sa.LargeBinary(), nullable=False),
        sa.Column('model', sa.String(64), nullable=False, server_default='nomic-embed-text'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['raw_job_id'], ['raw_jobs.id']),
        sa.PrimaryKeyConstraint('raw_job_id'),
    )

    # UserLearnProfile table
    op.create_table(
        'user_learn_profiles',
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('imported_centroid', sa.LargeBinary(), nullable=True),
        sa.Column('dismissed_centroid', sa.LargeBinary(), nullable=True),
        sa.Column('samples_imported', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('samples_dismissed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reason_counts', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('user_learn_profiles')
    op.drop_table('job_embeddings')
    with op.batch_alter_table('users') as batch:
        batch.drop_column('job_learn_weight_pct')
        batch.drop_column('job_learn_min_samples')
        batch.drop_column('job_learn_enabled')
    with op.batch_alter_table('job_matches') as batch:
        batch.drop_column('feedback_text')
        batch.drop_column('feedback_reasons')
