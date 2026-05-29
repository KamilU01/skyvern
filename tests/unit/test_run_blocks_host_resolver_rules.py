from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from skyvern.forge.sdk.core import skyvern_context
from skyvern.forge.sdk.core.skyvern_context import SkyvernContext
from skyvern.forge.sdk.routes import run_blocks
from skyvern.forge.sdk.workflow.models.workflow import WorkflowRunStatus
from skyvern.schemas.credential_type import CredentialType
from skyvern.schemas.run_blocks import DownloadFilesRequest, LoginRequest


async def _run_block_request(
    monkeypatch: pytest.MonkeyPatch,
    run_block_request,
):
    now = datetime.now(UTC)
    workflow_run = SimpleNamespace(
        workflow_run_id="wr_123",
        status=WorkflowRunStatus.created,
        failure_reason=None,
        created_at=now,
        modified_at=now,
    )
    run_workflow = AsyncMock(return_value=workflow_run)
    monkeypatch.setattr(run_blocks.workflow_service, "run_workflow", run_workflow)
    skyvern_context.reset()
    skyvern_context.set(SkyvernContext(request_id="req_123"))

    try:
        response = await run_blocks._run_workflow_and_build_response(
            request=MagicMock(),
            background_tasks=MagicMock(),
            new_workflow=SimpleNamespace(workflow_id="wf_123", title="Generated workflow"),
            workflow_id="wpid_123",
            organization=SimpleNamespace(organization_id="org_123"),
            run_block_request=run_block_request,
            webhook_url=run_block_request.webhook_url,
            totp_verification_url=run_block_request.totp_url,
            totp_identifier=run_block_request.totp_identifier,
            x_api_key=None,
        )
    finally:
        skyvern_context.reset()

    return response, run_workflow


@pytest.mark.asyncio
async def test_login_run_block_response_preserves_host_resolver_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_block_request = LoginRequest(
        credential_type=CredentialType.skyvern,
        host_resolver_rules="login.local:10.0.0.5",
    )

    response, run_workflow = await _run_block_request(monkeypatch, run_block_request)

    assert response.run_request is not None
    assert response.run_request.host_resolver_rules == "login.local:10.0.0.5"
    assert run_workflow.await_args.kwargs["workflow_request"].host_resolver_rules == "login.local:10.0.0.5"


@pytest.mark.asyncio
async def test_download_files_run_block_response_preserves_host_resolver_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_block_request = DownloadFilesRequest(
        navigation_goal="Download the invoice",
        host_resolver_rules="files.local:10.0.0.6",
    )

    response, run_workflow = await _run_block_request(monkeypatch, run_block_request)

    assert response.run_request is not None
    assert response.run_request.host_resolver_rules == "files.local:10.0.0.6"
    assert run_workflow.await_args.kwargs["workflow_request"].host_resolver_rules == "files.local:10.0.0.6"
