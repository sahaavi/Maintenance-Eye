from __future__ import annotations

import pytest

from agent.tools.work_order import manage_work_order  # type: ignore[import-not-found]
from tests.fixtures.factories import FakeEAM


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_create_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEAM()
    from agent.tools import work_order  # type: ignore[import-not-found]

    monkeypatch.setattr(work_order, "get_eam_service", lambda: fake)

    result = await manage_work_order(
        action="create",
        asset_id="AST-UNIT-001",
        description="Bracket corrosion",
        problem_code="ME-003",
        fault_code="WEAR-SUR",
        action_code="REPAIR",
        failure_class="MECHANICAL",
        priority="P2",
        notes="requires expedited review",
    )

    assert result["success"] is True
    assert result["action"] == "created"
    assert result["work_order"]["priority"] == "P2"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_rejects_invalid_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEAM()
    from agent.tools import work_order  # type: ignore[import-not-found]

    monkeypatch.setattr(work_order, "get_eam_service", lambda: fake)

    result = await manage_work_order(
        action="create",
        asset_id="AST-UNIT-001",
        description="Invalid priority test",
        priority="P0",
    )

    assert result["success"] is False
    assert "Invalid priority" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_list_by_status(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEAM()
    from agent.tools import work_order  # type: ignore[import-not-found]

    monkeypatch.setattr(work_order, "get_eam_service", lambda: fake)

    result = await manage_work_order(action="list", status="in_progress")
    assert result["success"] is True
    assert result["count"] >= 1
