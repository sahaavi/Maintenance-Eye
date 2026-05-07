from __future__ import annotations

import pytest
from models.schemas import (  # type: ignore[import-not-found]
    AssetStatus,
    Priority,
    WorkOrder,
    WorkOrderStatus,
)
from services.json_eam import JsonEAM  # type: ignore[import-not-found]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_eam_search_assets_query_and_station() -> None:
    eam = JsonEAM()

    all_assets = await eam.search_assets()
    assert all_assets

    first_station = all_assets[0].location.station
    station_filtered = await eam.search_assets(station=first_station)
    assert station_filtered
    assert all(first_station.lower() in a.location.station.lower() for a in station_filtered)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_eam_create_and_update_work_order() -> None:
    eam = JsonEAM()
    wo = WorkOrder(
        wo_id="",
        asset_id="AST-001",
        description="Unit test work order",
        problem_code="ME-003",
        fault_code="WEAR-SUR",
        action_code="REPAIR",
        failure_class="MECHANICAL",
        priority=Priority.P3_MEDIUM,
    )

    created = await eam.create_work_order(wo)
    assert created.wo_id.startswith("WO-")

    updated = await eam.update_work_order(
        created.wo_id,
        {"status": WorkOrderStatus.IN_PROGRESS, "priority": Priority.P2_HIGH},
    )
    assert updated is not None
    assert updated.status == WorkOrderStatus.IN_PROGRESS
    assert updated.priority == Priority.P2_HIGH


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_eam_returns_work_orders_latest_first_for_demo_asset() -> None:
    eam = JsonEAM()

    results = await eam.get_work_orders(asset_id="ESC-SC-003", status=WorkOrderStatus.OPEN)

    assert [wo.wo_id for wo in results[:2]] == ["WO-2026-0152", "WO-2026-0151"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_eam_switch_machine_demo_state_has_active_work_orders() -> None:
    eam = JsonEAM()

    switch_machines = await eam.search_assets(
        department="guideway",
        asset_type="switch_machine",
    )

    assert {asset.asset_id for asset in switch_machines} == {
        "SWM-RO-001",
        "SWM-GW-002",
        "SWM-LC-003",
        "SWM-RO-004",
    }
    assert {asset.status for asset in switch_machines} == {AssetStatus.OPERATIONAL}

    active_statuses = {WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS}
    for asset in switch_machines:
        work_orders = await eam.get_work_orders(asset_id=asset.asset_id)
        assert any(wo.status in active_statuses for wo in work_orders), asset.asset_id

    gateway_orders = await eam.get_work_orders(
        asset_id="SWM-GW-002",
        status=WorkOrderStatus.IN_PROGRESS,
    )
    assert [wo.wo_id for wo in gateway_orders] == ["WO-2026-0174"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_eam_robust_tokenization_and_metadata_search() -> None:
    eam = JsonEAM()

    # 1. Test tokenization: query "#1" should match asset with "1" in its name/ID
    # Most assets in seed data end with "#1", "#2", etc.
    results = await eam.search_assets(query="Escalator #1")
    assert results
    # With robust tokenization, "#1" becomes "1", which should match "Escalator #1"

    # 2. Test search WOs by asset metadata
    # Find an asset and search for its WOs by the asset's name
    all_assets = await eam.search_assets()
    asset = all_assets[0]
    asset_name_part = asset.name.split()[0]  # e.g., "Waterfront"

    results = await eam.search_work_orders(q=asset_name_part)
    # This should now work because we include asset metadata in WO search
    assert results
    assert any(wo.asset_id == asset.asset_id for wo in results)
