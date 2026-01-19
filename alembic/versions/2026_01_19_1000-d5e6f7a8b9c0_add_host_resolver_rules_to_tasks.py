"""add_host_resolver_rules_to_tasks

Revision ID: d5e6f7a8b9c0
Revises: c1a2b3d4e5f6
Create Date: 2026-01-19 10:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add host_resolver_rules column to tasks table
    op.add_column("tasks", sa.Column("host_resolver_rules", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "host_resolver_rules")
