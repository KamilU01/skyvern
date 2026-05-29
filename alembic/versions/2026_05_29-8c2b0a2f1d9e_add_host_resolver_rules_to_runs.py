"""add host resolver rules to runs

Revision ID: 8c2b0a2f1d9e
Revises: 78a8db531e69
Create Date: 2026-05-29 15:02:00.000000

"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c2b0a2f1d9e"
down_revision: Union[str, None] = "78a8db531e69"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("host_resolver_rules", sa.String(), nullable=True))
    op.add_column("workflow_runs", sa.Column("host_resolver_rules", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_runs", "host_resolver_rules")
    op.drop_column("tasks", "host_resolver_rules")
