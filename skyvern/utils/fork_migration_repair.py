"""Repair Skyvern databases stamped with a fork-only Alembic revision."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass


FORK_REVISION = "d5e6f7a8b9c0"
BASELINE_REVISION = "1faa2a5869cd"
HEAD_REVISION = "8c2b0a2f1d9e"
TASK_RUNS_COMPUTE_REVISION = "67784da0203e"
TASK_RUNS_MEMORY_REVISION = "174dcd456325"
PERSISTENT_BROWSER_SESSION_UNIQUE_REVISION = "cf6ae2f5013c"
SCRIPT_BLOCKS_INPUT_FIELDS_REVISION = "7ab8e817802a"
WORKFLOW_TEMPLATES_REVISION = "b4738bd17198"
FILE_SIZE_REVISION = "78a8db531e69"

Column = tuple[str, str]
Step = tuple[str, str]


@dataclass(frozen=True)
class Checkpoint:
    """Schema evidence that a cherry-picked Alembic revision has already run."""

    revision: str
    columns: frozenset[Column] = frozenset()
    tables: frozenset[str] = frozenset()
    relations: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RepairResult:
    """Outcome of a fork-only migration repair attempt."""

    current_revision: str | None
    steps: tuple[Step, ...]
    applied: bool

    @property
    def needed(self) -> bool:
        """Return whether this database needed the fork repair path."""
        return bool(self.steps)


CHERRY_PICKED_CHECKPOINTS = (
    Checkpoint(
        TASK_RUNS_COMPUTE_REVISION,
        columns=frozenset(
            {
                ("task_runs", "instance_type"),
                ("task_runs", "vcpu_millicores"),
                ("task_runs", "duration_ms"),
                ("task_runs", "compute_cost"),
            }
        ),
    ),
    Checkpoint(
        TASK_RUNS_MEMORY_REVISION,
        columns=frozenset({("task_runs", "memory_mb")}),
    ),
    Checkpoint(
        SCRIPT_BLOCKS_INPUT_FIELDS_REVISION,
        columns=frozenset({("script_blocks", "input_fields")}),
    ),
    Checkpoint(
        WORKFLOW_TEMPLATES_REVISION,
        tables=frozenset({"workflow_templates"}),
        columns=frozenset(
            {
                ("workflow_templates", "workflow_template_id"),
                ("workflow_templates", "workflow_permanent_id"),
                ("workflow_templates", "organization_id"),
                ("workflow_templates", "created_at"),
                ("workflow_templates", "modified_at"),
                ("workflow_templates", "deleted_at"),
            }
        ),
    ),
)

PERSISTENT_BROWSER_SESSION_UNIQUE_CHECKPOINT = Checkpoint(
    PERSISTENT_BROWSER_SESSION_UNIQUE_REVISION,
    relations=frozenset({"uc_persistent_browser_sessions_browser_address"}),
)

HOST_RESOLVER_RULES_CHECKPOINT = Checkpoint(
    HEAD_REVISION,
    columns=frozenset(
        {
            ("tasks", "host_resolver_rules"),
            ("workflow_runs", "host_resolver_rules"),
        }
    ),
)


def _has_all(required: Iterable, existing: set) -> bool:
    return all(item in existing for item in required)


def _has_any(required: Iterable, existing: set) -> bool:
    return any(item in existing for item in required)


def _checkpoint_present(
    checkpoint: Checkpoint,
    columns: set[Column],
    tables: set[str],
    relations: set[str],
) -> bool:
    required_columns = set(checkpoint.columns)
    required_tables = set(checkpoint.tables)
    required_relations = set(checkpoint.relations)
    all_present = (
        _has_all(required_columns, columns)
        and _has_all(required_tables, tables)
        and _has_all(required_relations, relations)
    )
    any_present = (
        _has_any(required_columns, columns)
        or _has_any(required_tables, tables)
        or _has_any(required_relations, relations)
    )
    if any_present and not all_present:
        missing_columns = sorted(required_columns - columns)
        missing_tables = sorted(required_tables - tables)
        missing_relations = sorted(required_relations - relations)
        details = []
        if missing_tables:
            details.append(f"missing tables: {', '.join(missing_tables)}")
        if missing_relations:
            details.append(f"missing relations: {', '.join(missing_relations)}")
        if missing_columns:
            details.append("missing columns: " + ", ".join(f"{table}.{column}" for table, column in missing_columns))
        raise ValueError(f"Revision {checkpoint.revision} is partially present; " + "; ".join(details))
    return all_present


def build_repair_steps(
    current_revision: str | None,
    existing_columns: set[Column],
    existing_tables: set[str],
    existing_relations: set[str] | None = None,
) -> list[Step]:
    """Build the ordered repair steps for a fork-stamped Skyvern database."""
    existing_relations = existing_relations or set()

    if current_revision is None:
        return []
    if current_revision == HEAD_REVISION:
        return []
    recoverable_revisions = {
        FORK_REVISION,
        BASELINE_REVISION,
        TASK_RUNS_COMPUTE_REVISION,
        TASK_RUNS_MEMORY_REVISION,
        PERSISTENT_BROWSER_SESSION_UNIQUE_REVISION,
        SCRIPT_BLOCKS_INPUT_FIELDS_REVISION,
        WORKFLOW_TEMPLATES_REVISION,
        FILE_SIZE_REVISION,
    }
    if current_revision not in recoverable_revisions:
        return []

    steps: list[Step] = []
    repairing_fork_revision = current_revision == FORK_REVISION
    if repairing_fork_revision:
        steps.append(("stamp", BASELINE_REVISION))
        current_revision = BASELINE_REVISION

    started_repair = repairing_fork_revision

    def continue_or_stop(checkpoint: Checkpoint, action_if_missing: Step) -> bool:
        nonlocal started_repair
        if _checkpoint_present(checkpoint, existing_columns, existing_tables, existing_relations):
            steps.append(("stamp", checkpoint.revision))
            started_repair = True
            return True
        if started_repair:
            steps.append(action_if_missing)
            return True
        return False

    if current_revision == BASELINE_REVISION:
        if not continue_or_stop(CHERRY_PICKED_CHECKPOINTS[0], ("upgrade", TASK_RUNS_COMPUTE_REVISION)):
            return []
        current_revision = TASK_RUNS_COMPUTE_REVISION

    if current_revision == TASK_RUNS_COMPUTE_REVISION:
        if not continue_or_stop(CHERRY_PICKED_CHECKPOINTS[1], ("upgrade", TASK_RUNS_MEMORY_REVISION)):
            return []
        current_revision = TASK_RUNS_MEMORY_REVISION

    if current_revision == TASK_RUNS_MEMORY_REVISION:
        if not continue_or_stop(
            PERSISTENT_BROWSER_SESSION_UNIQUE_CHECKPOINT,
            ("upgrade", PERSISTENT_BROWSER_SESSION_UNIQUE_REVISION),
        ):
            return []
        current_revision = PERSISTENT_BROWSER_SESSION_UNIQUE_REVISION

    if current_revision == PERSISTENT_BROWSER_SESSION_UNIQUE_REVISION:
        if not continue_or_stop(CHERRY_PICKED_CHECKPOINTS[2], ("upgrade", SCRIPT_BLOCKS_INPUT_FIELDS_REVISION)):
            return steps if started_repair else []
        current_revision = SCRIPT_BLOCKS_INPUT_FIELDS_REVISION

    if current_revision == SCRIPT_BLOCKS_INPUT_FIELDS_REVISION:
        if _checkpoint_present(CHERRY_PICKED_CHECKPOINTS[3], existing_columns, existing_tables, existing_relations):
            steps.append(("ensure", "workflow_templates_metadata"))
            steps.append(("stamp", WORKFLOW_TEMPLATES_REVISION))
            started_repair = True
        elif started_repair:
            steps.append(("upgrade", WORKFLOW_TEMPLATES_REVISION))
        else:
            return []
        current_revision = WORKFLOW_TEMPLATES_REVISION

    if _checkpoint_present(HOST_RESOLVER_RULES_CHECKPOINT, existing_columns, existing_tables, existing_relations):
        steps.append(("upgrade", FILE_SIZE_REVISION))
        steps.append(("stamp", HEAD_REVISION))
    elif started_repair:
        steps.append(("upgrade", "head"))
    else:
        return []

    steps.append(("check", "head"))
    return steps


def normalize_database_string(database_string: str) -> str:
    """Convert SQLAlchemy async/driver-specific Postgres URLs to psycopg URLs."""
    return database_string.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def is_postgresql_database(database_string: str) -> bool:
    """Return whether the connection string points at PostgreSQL."""
    return database_string.startswith(("postgresql://", "postgresql+psycopg://", "postgresql+asyncpg://"))


def connect(database_string: str):
    """Open a synchronous psycopg connection for metadata-only repair checks."""
    import psycopg

    return psycopg.connect(normalize_database_string(database_string))


def fetch_current_revision(conn) -> str | None:
    """Return the single Alembic revision stamped in the database, if present."""
    try:
        with conn.cursor() as cur:
            cur.execute("select version_num from alembic_version")
            rows = cur.fetchall()
    except Exception as exc:
        if exc.__class__.__name__ == "UndefinedTable":
            conn.rollback()
            return None
        raise
    if len(rows) == 0:
        return None
    if len(rows) != 1:
        raise RuntimeError(f"Expected at most one row in alembic_version, got {len(rows)}")
    return rows[0][0]


def fetch_schema(conn) -> tuple[set[Column], set[str], set[str]]:
    """Fetch public table and column names used as repair checkpoints."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select table_name, column_name
            from information_schema.columns
            where table_schema = 'public'
            """
        )
        columns = {(table, column) for table, column in cur.fetchall()}
        cur.execute(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
            """
        )
        tables = {row[0] for row in cur.fetchall()}
        cur.execute(
            """
            select relname
            from pg_class
            join pg_namespace on pg_namespace.oid = pg_class.relnamespace
            where pg_namespace.nspname = 'public'
            """
        )
        relations = {row[0] for row in cur.fetchall()}
    return columns, tables, relations


def stamp_revision(conn, revision: str) -> None:
    """Update alembic_version to a known upstream revision."""
    with conn.cursor() as cur:
        cur.execute("update alembic_version set version_num = %s", (revision,))
        if cur.rowcount != 1:
            raise RuntimeError(f"Expected to update one alembic_version row, updated {cur.rowcount}")
    conn.commit()


def ensure_workflow_templates_metadata(conn) -> None:
    """Ensure constraints and indexes exist when workflow_templates was cherry-picked."""
    with conn.cursor() as cur:
        cur.execute(
            """
            do $$
            begin
                if not exists (
                    select 1
                    from pg_constraint
                    where conname = 'workflow_templates_pkey'
                      and conrelid = 'workflow_templates'::regclass
                ) then
                    alter table workflow_templates
                    add constraint workflow_templates_pkey
                    primary key (workflow_template_id);
                end if;
            end
            $$;
            """
        )
        cur.execute(
            """
            do $$
            begin
                if not exists (
                    select 1
                    from pg_constraint
                    where conname = 'workflow_templates_organization_id_fkey'
                      and conrelid = 'workflow_templates'::regclass
                ) then
                    alter table workflow_templates
                    add constraint workflow_templates_organization_id_fkey
                    foreign key (organization_id)
                    references organizations (organization_id);
                end if;
            end
            $$;
            """
        )
        cur.execute(
            """
            create index if not exists ix_workflow_templates_organization_id
            on workflow_templates (organization_id)
            """
        )
        cur.execute(
            """
            create index if not exists ix_workflow_templates_workflow_permanent_id
            on workflow_templates (workflow_permanent_id)
            """
        )
    conn.commit()


def run_alembic(target: str, *, cwd: str, env: dict[str, str], check: bool = False) -> None:
    """Run an Alembic command in the application directory."""
    command = (
        [sys.executable, "-m", "alembic", "check"]
        if check
        else [
            sys.executable,
            "-m",
            "alembic",
            "upgrade",
            target,
        ]
    )
    subprocess.run(command, cwd=cwd, env=env, check=True)


def format_steps(steps: list[Step] | tuple[Step, ...]) -> str:
    """Format repair steps for logs and dry runs."""
    return "\n".join(f"{index + 1}. {action} {target}" for index, (action, target) in enumerate(steps))


def repair_if_needed(
    database_string: str,
    *,
    app_dir: str,
    apply: bool = True,
    reporter: Callable[[str], None] | None = None,
) -> RepairResult:
    """Repair a database stamped with the fork-only 1.0.7 revision, if needed."""
    if not database_string or not is_postgresql_database(database_string):
        return RepairResult(current_revision=None, steps=(), applied=False)

    def report(message: str) -> None:
        if reporter is not None:
            reporter(message)

    with connect(database_string) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_advisory_lock(hashtext('skyvern_fork_1_0_7_repair'))")
        current_revision = fetch_current_revision(conn)
        existing_columns, existing_tables, existing_relations = fetch_schema(conn)
        steps = tuple(build_repair_steps(current_revision, existing_columns, existing_tables, existing_relations))

        if not steps:
            return RepairResult(current_revision=current_revision, steps=(), applied=False)

        report("Detected Skyvern fork-only Alembic revision; repairing migration history.")
        report("Planned repair steps:")
        report(format_steps(steps))

        if not apply:
            return RepairResult(current_revision=current_revision, steps=steps, applied=False)

        env = os.environ.copy()
        env["DATABASE_STRING"] = database_string

        for action, target in steps:
            report(f"Running: {action} {target}")
            if action == "stamp":
                stamp_revision(conn, target)
            elif action == "upgrade":
                run_alembic(target, cwd=app_dir, env=env)
            elif action == "ensure" and target == "workflow_templates_metadata":
                ensure_workflow_templates_metadata(conn)
            elif action == "check":
                run_alembic(target, cwd=app_dir, env=env, check=True)
            else:
                raise RuntimeError(f"Unknown action: {action}")

        report("Skyvern fork migration repair completed.")
        return RepairResult(current_revision=current_revision, steps=steps, applied=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the fork migration repair utility."""
    parser = argparse.ArgumentParser(
        description="Repair Skyvern databases stamped with fork-only revision d5e6f7a8b9c0."
    )
    parser.add_argument(
        "--database-string",
        default=os.environ.get("DATABASE_STRING"),
        help="Skyvern DATABASE_STRING. Defaults to the DATABASE_STRING environment variable.",
    )
    parser.add_argument(
        "--app-dir",
        default=os.getcwd(),
        help="Skyvern application directory containing alembic.ini. Defaults to the current directory.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply changes. Without this flag the script prints the planned steps only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the fork migration repair utility."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not args.database_string:
        print("DATABASE_STRING is required.", file=sys.stderr)
        return 2

    result = repair_if_needed(
        args.database_string,
        app_dir=args.app_dir,
        apply=args.yes,
        reporter=print,
    )
    if not result.needed:
        print("No Skyvern fork migration repair needed.")
    elif not args.yes:
        print("\nDry run only. Re-run with --yes to apply these steps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
