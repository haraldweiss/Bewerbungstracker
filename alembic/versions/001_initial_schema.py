"""Initial schema: users, applications, emails, api_calls

Revision ID: 001
Revises:
Create Date: 2026-04-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema."""
    # users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('imap_host', sa.String(255), nullable=True),
        sa.Column('imap_user', sa.String(255), nullable=True),
        sa.Column('imap_password_encrypted', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    # sessions table
    op.create_table(
        'sessions',
        sa.Column('token', sa.String(500), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_sessions_expires_at', 'sessions', ['expires_at'])

    # applications table
    op.create_table(
        'applications',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('position', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('applied_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_applications_user_id', 'applications', ['user_id'])

    # emails table
    op.create_table(
        'emails',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('message_id', sa.String(500), nullable=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('from_address', sa.String(255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('matched_application_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['matched_application_id'], ['applications.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.UniqueConstraint('user_id', 'message_id', name='uix_user_message_id')
    )
    op.create_index('ix_emails_user_id', 'emails', ['user_id'])

    # api_calls table
    op.create_table(
        'api_calls',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('cost', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index('ix_api_calls_user_id', 'api_calls', ['user_id'])
    op.create_index('ix_api_calls_timestamp', 'api_calls', ['timestamp'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('api_calls')
    op.drop_table('emails')
    op.drop_table('applications')
    op.drop_table('sessions')
    op.drop_table('users')
