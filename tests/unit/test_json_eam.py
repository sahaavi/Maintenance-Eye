from __future__ import annotations

import pytest

from models.schemas import Priority, WorkOrder, WorkOrderStatus  # type: ignore[import-not-found]
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
    asset_name_part = asset.name.split()[0] # e.g., "Waterfront"
    
    results = await eam.search_work_orders(q=asset_name_part)
    # This should now work because we include asset metadata in WO search
    assert results
    assert any(wo.asset_id == asset.asset_id for wo in results)
