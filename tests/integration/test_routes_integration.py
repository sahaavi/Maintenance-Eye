from __future__ import annotations

import re

import pytest


@pytest.mark.integration
@pytest.mark.api
def test_assets_route_returns_seeded_asset(client) -> None:
    response = client.get("/api/assets/AST-UNIT-001")
    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == "AST-UNIT-001"


@pytest.mark.integration
@pytest.mark.api
def test_work_orders_invalid_status_returns_400(client) -> None:
    response = client.get("/api/work-orders", params={"status": "not-a-status"})
    assert response.status_code == 400
    assert "Invalid status" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.api
def test_work_order_advanced_search_filters(client) -> None:
    response = client.get("/api/work-orders", params={"q": "Surface wear", "priority": "P3"})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row["priority"] == "P3" for row in rows)


@pytest.mark.integration
@pytest.mark.api
def test_work_order_routes_return_latest_first(fake_eam, client) -> None:
    fake_eam.work_orders[0].created_at = "2026-01-01T00:00:00"
    fake_eam.work_orders[1].created_at = "2026-02-01T00:00:00"

    direct = client.get("/api/work-orders")
    assert direct.status_code == 200
    assert [row["wo_id"] for row in direct.json()[:2]] == ["WO-2026-0002", "WO-2026-0001"]

    advanced = client.get("/api/work-orders", params={"q": "Surface wear"})
    assert advanced.status_code == 200
    assert [row["wo_id"] for row in advanced.json()[:2]] == [
        "WO-2026-0002",
        "WO-2026-0001",
    ]


@pytest.mark.integration
@pytest.mark.api
def test_generated_report_links_are_retrievable(patch_eam, client) -> None:
    from agent.tools import report_generator  # type: ignore[import-not-found]

    patch_eam(report_generator)

    generated = client.post("/api/reports/generate", params={"asset_id": "AST-UNIT-001"})
    assert generated.status_code == 200
    match = re.search(r"RPT-\d{8}-\d{6}", generated.text)
    assert match

    linked = client.get(f"/api/reports/{match.group(0)}")
    assert linked.status_code == 200
    assert "Signal Cabinet" in linked.text


@pytest.mark.integration
@pytest.mark.api
def test_locations_endpoint_returns_aggregated_counts(client) -> None:
    response = client.get("/api/locations")
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all("asset_count" in item for item in body)
