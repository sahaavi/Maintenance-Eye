from __future__ import annotations

import pytest


@pytest.mark.api
def test_assets_contract_shape(client) -> None:
    response = client.get("/api/assets", params={"q": "signal"})
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)
    assert rows

    first = rows[0]
    for key in ["asset_id", "name", "department", "location", "status"]:
        assert key in first


@pytest.mark.api
def test_eam_codes_contract_shape(client) -> None:
    response = client.get("/api/eam-codes")
    assert response.status_code == 200
    rows = response.json()
    assert rows

    first = rows[0]
    required = ["code_type", "code", "label", "department", "asset_types", "description"]
    for field in required:
        assert field in first


@pytest.mark.api
@pytest.mark.regression
def test_work_orders_status_filter_is_case_insensitive(client) -> None:
    response = client.get("/api/work-orders", params={"status": "IN_PROGRESS"})
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row["status"] == "in_progress" for row in rows)
