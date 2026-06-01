import pytest

from skyvern.utils.fork_migration_repair import (
    BASELINE_REVISION,
    FORK_REVISION,
    HEAD_REVISION,
    build_repair_steps,
)


def test_build_repair_steps_noops_for_unrelated_revision() -> None:
    assert build_repair_steps("67784da0203e", set(), set()) == []


def test_build_repair_steps_repairs_fork_revision_with_cherry_picked_schema() -> None:
    existing_columns = {
        ("task_runs", "instance_type"),
        ("task_runs", "vcpu_millicores"),
        ("task_runs", "duration_ms"),
        ("task_runs", "compute_cost"),
        ("task_runs", "memory_mb"),
        ("script_blocks", "input_fields"),
        ("workflow_templates", "workflow_template_id"),
        ("workflow_templates", "workflow_permanent_id"),
        ("workflow_templates", "organization_id"),
        ("workflow_templates", "created_at"),
        ("workflow_templates", "modified_at"),
        ("workflow_templates", "deleted_at"),
    }
    existing_tables = {"workflow_templates"}

    assert build_repair_steps(FORK_REVISION, existing_columns, existing_tables) == [
        ("stamp", BASELINE_REVISION),
        ("stamp", "67784da0203e"),
        ("stamp", "174dcd456325"),
        ("upgrade", "cf6ae2f5013c"),
        ("stamp", "7ab8e817802a"),
        ("ensure", "workflow_templates_metadata"),
        ("stamp", "b4738bd17198"),
        ("upgrade", "head"),
        ("check", "head"),
    ]


def test_build_repair_steps_stamps_existing_browser_address_constraint() -> None:
    steps = build_repair_steps(
        FORK_REVISION,
        set(),
        set(),
        {"uc_persistent_browser_sessions_browser_address"},
    )

    assert ("upgrade", "cf6ae2f5013c") not in steps
    assert ("stamp", "cf6ae2f5013c") in steps


def test_build_repair_steps_recovers_after_failed_browser_address_constraint_upgrade() -> None:
    steps = build_repair_steps(
        "174dcd456325",
        set(),
        set(),
        {"uc_persistent_browser_sessions_browser_address"},
    )

    assert steps[0] == ("stamp", "cf6ae2f5013c")
    assert ("upgrade", "cf6ae2f5013c") not in steps


def test_build_repair_steps_stamps_head_when_host_resolver_columns_already_exist() -> None:
    existing_columns = {
        ("tasks", "host_resolver_rules"),
        ("workflow_runs", "host_resolver_rules"),
    }

    steps = build_repair_steps(FORK_REVISION, existing_columns, set())

    assert steps[-3:] == [
        ("upgrade", "78a8db531e69"),
        ("stamp", HEAD_REVISION),
        ("check", "head"),
    ]


def test_build_repair_steps_rejects_partially_present_checkpoint() -> None:
    with pytest.raises(ValueError, match="partially present"):
        build_repair_steps(FORK_REVISION, {("task_runs", "instance_type")}, set())
