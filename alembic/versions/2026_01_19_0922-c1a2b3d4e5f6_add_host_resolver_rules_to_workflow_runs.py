"""add_host_resolver_rules_to_workflow_runs

Revision ID: c1a2b3d4e5f6
Revises: b4738bd17198
Create Date: 2026-01-19 09:22:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "b4738bd17198"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add host_resolver_rules column to workflow_runs table
    op.add_column("workflow_runs", sa.Column("host_resolver_rules", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_runs", "host_resolver_rules")
