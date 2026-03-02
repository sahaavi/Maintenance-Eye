from __future__ import annotations

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
def test_locations_endpoint_returns_aggregated_counts(client) -> None:
    response = client.get("/api/locations")
    assert response.status_code == 200
    body = response.json()
    assert body
    assert all("asset_count" in item for item in body)
