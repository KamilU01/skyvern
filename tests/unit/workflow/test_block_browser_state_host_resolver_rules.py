from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from skyvern.forge.sdk.workflow.models import block as block_module
from skyvern.forge.sdk.workflow.models.block import Block
from skyvern.forge.sdk.workflow.models.parameter import OutputParameter, ParameterType
from skyvern.schemas.workflows import BlockResult, BlockType


class _ConcreteBlock(Block):
    """Concrete block for testing shared Block helpers."""

    async def execute(
        self,
        workflow_run_id: str,
        workflow_run_block_id: str,
        organization_id: str | None = None,
        browser_session_id: str | None = None,
        **kwargs: dict,
    ) -> BlockResult:
        raise NotImplementedError

    def get_all_parameters(self, workflow_run_id: str) -> list[Any]:
        return []


def _output_parameter() -> OutputParameter:
    now = datetime.now(UTC)
    return OutputParameter(
        parameter_type=ParameterType.OUTPUT,
        key="test_output",
        output_parameter_id="op_test",
        workflow_id="wf_test",
        created_at=now,
        modified_at=now,
    )


@pytest.mark.asyncio
async def test_get_or_create_browser_state_repairs_with_host_resolver_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow_run = SimpleNamespace(
        workflow_run_id="wr_123",
        workflow_permanent_id="wpid_123",
        organization_id="org_123",
        browser_profile_id="bp_123",
        proxy_location=None,
        extra_http_headers=None,
        browser_address=None,
        host_resolver_rules="app.local:10.0.0.5",
    )
    browser_state = SimpleNamespace(check_and_fix_state=AsyncMock())
    fake_app = SimpleNamespace(
        BROWSER_MANAGER=SimpleNamespace(
            get_for_workflow_run=MagicMock(return_value=None),
            get_or_create_for_workflow_run=AsyncMock(return_value=browser_state),
        ),
        WORKFLOW_SERVICE=SimpleNamespace(get_workflow_run=AsyncMock(return_value=workflow_run)),
    )
    monkeypatch.setattr(block_module, "app", fake_app)

    block = _ConcreteBlock(
        label="test",
        block_type=BlockType.WAIT,
        output_parameter=_output_parameter(),
    )

    result = await block.get_or_create_browser_state(
        workflow_run_id="wr_123",
        organization_id="org_123",
    )

    assert result is browser_state
    browser_state.check_and_fix_state.assert_awaited_once()
    assert (
        browser_state.check_and_fix_state.await_args.kwargs["host_resolver_rules"]
        == "app.local:10.0.0.5"
    )
