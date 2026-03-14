from __future__ import annotations

import pytest
from agent.tools.confirm_action import (  # type: ignore[import-not-found]
    propose_action,
    set_session_context,
)


@pytest.mark.asyncio
async def test_propose_action_create_requires_asset_id() -> None:
    set_session_context("unit-confirm-session-asset")

    result = propose_action(
        action_type="create_work_order",
        description="Bearing vibration requires follow-up",
        asset_id="",
        priority="P2",
        confidence=0.9,
    )

    assert result["success"] is False
    assert result.get("missing_fields") == ["asset_id"]


@pytest.mark.asyncio
async def test_propose_action_create_requires_description() -> None:
    set_session_context("unit-confirm-session-description")

    result = propose_action(
        action_type="create_work_order",
        description="",
        asset_id="AST-UNIT-001",
        priority="P2",
        confidence=0.9,
    )

    assert result["success"] is False
    assert result.get("missing_fields") == ["description"]
