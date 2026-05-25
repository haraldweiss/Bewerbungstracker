"""add task_queue table

Revision ID: f0778653c386
Revises: b3e4f5a6c7d8
Create Date: 2026-05-25 17:51:35.693510

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0778653c386'
down_revision = 'b3e4f5a6c7d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'task_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('type', sa.String(64), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('payload', sa.Text, nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('result', sa.Text, nullable=True),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('progress', sa.Integer, nullable=False, server_default='0'),
        sa.Column('attempts', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer, nullable=False, server_default='3'),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('finished_at', sa.DateTime, nullable=True),
        sa.Column('heartbeat_at', sa.DateTime, nullable=True),
        sa.Column('worker_id', sa.String(128), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index(
        'idx_task_queue_pickup', 'task_queue',
        ['status', 'priority', 'created_at'],
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        'idx_task_queue_user', 'task_queue',
        ['user_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('idx_task_queue_user', table_name='task_queue')
    op.drop_index('idx_task_queue_pickup', table_name='task_queue')
    op.drop_table('task_queue')
