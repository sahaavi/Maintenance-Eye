from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes import router as api_router  # type: ignore[import-not-found]


@pytest.mark.system
def test_system_health_and_routes_load_without_external_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import firestore_eam  # type: ignore[import-not-found]
    from tests.fixtures.factories import FakeEAM

    monkeypatch.setattr(firestore_eam, "_eam_service", FakeEAM(), raising=False)
    monkeypatch.setattr(firestore_eam, "get_eam_service", lambda: firestore_eam._eam_service, raising=True)

    app = FastAPI(title="system-test-app")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    app.include_router(api_router, prefix="/api")

    with TestClient(app) as client:
        health_response = client.get("/health")
        assets_response = client.get("/api/assets")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "healthy"
    assert assets_response.status_code == 200
    assert len(assets_response.json()) >= 1
