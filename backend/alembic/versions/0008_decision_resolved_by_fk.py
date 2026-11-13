"""Add the missing foreign key scheduling_decisions.resolved_by -> users.id.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None

_FK = "fk_scheduling_decisions_resolved_by_users"


def upgrade() -> None:
    with op.batch_alter_table("scheduling_decisions") as batch:
        batch.create_foreign_key(_FK, "users", ["resolved_by"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("scheduling_decisions") as batch:
        batch.drop_constraint(_FK, type_="foreignkey")
