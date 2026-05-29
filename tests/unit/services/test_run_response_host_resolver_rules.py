from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from skyvern.forge.sdk.schemas.task_v2 import TaskV2, TaskV2Status
from skyvern.forge.sdk.schemas.tasks import TaskBase, TaskResponse, TaskStatus
from skyvern.schemas.runs import RunEngine, RunType, WorkflowRunRequest
from skyvern.services import run_service, task_v2_service, workflow_service


@pytest.mark.asyncio
async def test_get_run_response_preserves_task_v1_host_resolver_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    task_response = TaskResponse(
        request=TaskBase(
            url="https://example.com",
            navigation_goal="Test task",
            host_resolver_rules="example.com:192.168.1.100",
        ),
        task_id="tsk_123",
        status=TaskStatus.completed,
        created_at=now,
        modified_at=now,
    )
    fake_app = SimpleNamespace(
        DATABASE=SimpleNamespace(
            tasks=SimpleNamespace(
                get_run=AsyncMock(
                    return_value=SimpleNamespace(
                        run_id="tsk_123",
                        task_run_type=RunType.task_v1,
                    )
                ),
            ),
        ),
    )
    monkeypatch.setattr(run_service, "app", fake_app)
    monkeypatch.setattr(
        run_service.task_v1_service,
        "get_task_v1_response",
        AsyncMock(return_value=task_response),
    )

    response = await run_service.get_run_response("tsk_123", organization_id="org_123")

    assert response is not None
    assert response.run_request is not None
    assert response.run_request.engine is RunEngine.skyvern_v1
    assert response.run_request.host_resolver_rules == "example.com:192.168.1.100"


@pytest.mark.asyncio
async def test_build_task_v2_run_response_preserves_workflow_host_resolver_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    task_v2 = TaskV2(
        task_id="tsk_v2_123",
        status=TaskV2Status.completed,
        organization_id="org_123",
        workflow_run_id="wr_123",
        prompt="Test task v2",
        url="https://example.com",
        created_at=now,
        modified_at=now,
    )
    workflow_run_response = SimpleNamespace(
        failure_reason=None,
        recording_url=None,
        screenshot_urls=None,
        downloaded_files=None,
        run_request=WorkflowRunRequest(
            workflow_id="wpid_123",
            host_resolver_rules="app.local:10.0.0.5",
        ),
        errors=None,
        step_count=None,
    )
    monkeypatch.setattr(
        workflow_service,
        "get_workflow_run_response",
        AsyncMock(return_value=workflow_run_response),
    )

    response = await task_v2_service.build_task_v2_run_response(task_v2)

    assert response.run_request is not None
    assert response.run_request.host_resolver_rules == "app.local:10.0.0.5"
