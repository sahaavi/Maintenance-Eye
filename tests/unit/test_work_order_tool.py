from __future__ import annotations

import pytest
from agent.tools.work_order import manage_work_order  # type: ignore[import-not-found]
from services.json_eam import JsonEAM  # type: ignore[import-not-found]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_create_success(patch_eam) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    patch_eam(work_order)

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
async def test_manage_work_order_create_requires_asset_id(patch_eam) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    patch_eam(work_order)

    result = await manage_work_order(
        action="create",
        asset_id="",
        description="Missing asset id",
    )

    assert result["success"] is False
    assert result.get("missing_fields") == ["asset_id"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_create_requires_description(patch_eam) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    patch_eam(work_order)

    result = await manage_work_order(
        action="create",
        asset_id="AST-UNIT-001",
        description="",
    )

    assert result["success"] is False
    assert result.get("missing_fields") == ["description"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_rejects_invalid_priority(patch_eam) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    patch_eam(work_order)

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
async def test_manage_work_order_list_by_status(patch_eam) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    patch_eam(work_order)

    result = await manage_work_order(action="list", status="in_progress")
    assert result["success"] is True
    assert result["count"] >= 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_search_handles_spoken_asset_id_phrase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    monkeypatch.setattr(work_order, "get_eam_service", lambda: JsonEAM())

    result = await manage_work_order(
        action="search",
        description="open work orders for e s c dash s c dash zero zero three",
    )

    assert result["success"] is True
    wo_ids = {wo["wo_id"] for wo in result["work_orders"]}
    assert "WO-2026-0151" in wo_ids
    assert "WO-2026-0152" in wo_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_manage_work_order_search_suggests_confirmation_for_malformed_asset_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.tools import work_order  # type: ignore[import-not-found]

    monkeypatch.setattr(work_order, "get_eam_service", lambda: JsonEAM())

    result = await manage_work_order(
        action="search",
        description="are there any work order for rc 139",
    )

    assert result["success"] is True
    assert result["count"] == 0
    assert result.get("needs_asset_confirmation") is True
    guessed = result.get("guessed_assets", [])
    assert guessed
    assert guessed[0]["asset_id"] == "TC-139"
