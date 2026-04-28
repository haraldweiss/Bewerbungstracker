"""Add envelope encryption columns to users

Revision ID: a1b2c3d4e5f6
Revises: 6282fb5759aa
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '6282fb5759aa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-User-Salt + verschlüsselter DEK für Envelope-Encryption.
    # Beide nullable, damit Bestands-User (falls vorhanden) ohne Schema-Crash
    # weiterleben – auth-Pfad behandelt None korrekt (überspringt DEK-Unlock).
    op.add_column('users', sa.Column('encryption_salt', sa.LargeBinary(length=16), nullable=True))
    op.add_column('users', sa.Column('encrypted_data_key', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'encrypted_data_key')
    op.drop_column('users', 'encryption_salt')
