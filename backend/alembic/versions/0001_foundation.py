"""Create the initial migration baseline.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-11-02

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Establish the migration head; application tables arrive in later milestones."""


def downgrade() -> None:
    """Remove the empty foundation revision."""
