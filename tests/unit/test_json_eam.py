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
async def test_json_eam_search_work_orders_with_location_join() -> None:
    eam = JsonEAM()
    locations = await eam.get_locations()
    assert locations

    station = locations[0]["station"]
    results = await eam.search_work_orders(location=station)
    assert isinstance(results, list)
