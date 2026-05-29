from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from skyvern.forge.sdk.routes import agent_protocol
from skyvern.forge.sdk.schemas.task_v2 import TaskV2, TaskV2Request, TaskV2Status


async def _run_legacy_task_v2(
    monkeypatch: pytest.MonkeyPatch,
    data: TaskV2Request,
) -> tuple[dict, AsyncMock]:
    now = datetime.now(UTC)
    task_v2 = TaskV2(
        task_id="tsk_v2_123",
        status=TaskV2Status.created,
        organization_id="org_123",
        prompt=data.user_prompt,
        url=data.url,
        created_at=now,
        modified_at=now,
    )
    initialize_task_v2 = AsyncMock(return_value=task_v2)
    execute_task_v2 = AsyncMock()

    monkeypatch.setattr(
        agent_protocol.PermissionCheckerFactory,
        "get_instance",
        MagicMock(return_value=SimpleNamespace(check=AsyncMock())),
    )
    monkeypatch.setattr(
        agent_protocol.AsyncExecutorFactory,
        "get_executor",
        MagicMock(return_value=SimpleNamespace(execute_task_v2=execute_task_v2)),
    )
    monkeypatch.setattr(
        agent_protocol,
        "app",
        SimpleNamespace(RATE_LIMITER=SimpleNamespace(rate_limit_submit_run=AsyncMock())),
    )
    monkeypatch.setattr(agent_protocol.task_v2_service, "initialize_task_v2", initialize_task_v2)
    monkeypatch.setattr(agent_protocol.analytics, "capture", MagicMock())

    response = await agent_protocol.run_task_v2(
        request=MagicMock(),
        background_tasks=MagicMock(),
        data=data,
        organization=SimpleNamespace(organization_id="org_123"),
    )

    return response, initialize_task_v2


@pytest.mark.asyncio
async def test_legacy_task_v2_request_without_host_resolver_rules_does_not_break(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = TaskV2Request(user_prompt="Do the task", url="https://example.com")

    response, initialize_task_v2 = await _run_legacy_task_v2(monkeypatch, data)

    assert response["task_id"] == "tsk_v2_123"
    assert initialize_task_v2.await_args.kwargs["host_resolver_rules"] is None


@pytest.mark.asyncio
async def test_legacy_task_v2_request_passes_host_resolver_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = TaskV2Request(
        user_prompt="Do the task",
        url="https://example.com",
        host_resolver_rules="example.com:192.168.1.100",
    )

    _, initialize_task_v2 = await _run_legacy_task_v2(monkeypatch, data)

    assert initialize_task_v2.await_args.kwargs["host_resolver_rules"] == "example.com:192.168.1.100"
