"""add User.onboarding_complete + User.onboarding_data

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-06-08 12:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "b0c1d2e3f4a5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_data",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_data")
    op.drop_column("users", "onboarding_complete")
