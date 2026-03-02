from __future__ import annotations

import pytest


@pytest.mark.security
@pytest.mark.api
def test_invalid_status_input_does_not_trigger_server_error(client) -> None:
    malicious = "in_progress' OR 1=1 --"
    response = client.get("/api/work-orders", params={"status": malicious})
    assert response.status_code == 400
    assert "Invalid status" in response.json()["detail"]


@pytest.mark.security
@pytest.mark.api
def test_asset_lookup_not_found_response_is_controlled(client) -> None:
    response = client.get("/api/assets/AST-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found"


@pytest.mark.security
def test_confirmation_endpoints_do_not_expose_tracebacks(client) -> None:
    response = client.post("/api/sessions/sx/confirm/not-real")
    assert response.status_code == 404
    body = response.text.lower()
    assert "traceback" not in body
