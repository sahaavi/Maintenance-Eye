from __future__ import annotations

import pytest
from api.routes import router as api_router  # type: ignore[import-not-found]
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient


@pytest.mark.system
def test_system_health_and_routes_load_without_external_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import eam_provider  # type: ignore[import-not-found]

    from tests.fixtures.factories import FakeEAM

    monkeypatch.setattr(eam_provider, "_eam_service", FakeEAM(), raising=False)
    monkeypatch.setattr(
        eam_provider, "get_eam_service", lambda: eam_provider._eam_service, raising=True
    )

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


@pytest.mark.system
@pytest.mark.asyncio
async def test_readiness_uses_eam_interface_search_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from main import readiness_check  # type: ignore[import-not-found]
    from services import eam_provider  # type: ignore[import-not-found]

    class InterfaceOnlyEAM:
        async def search_assets(
            self,
            query: str = "",
            department: str = "",
            station: str = "",
            asset_type: str = "",
        ) -> list:
            return []

    monkeypatch.setattr(eam_provider, "get_eam_service", lambda: InterfaceOnlyEAM())

    response = await readiness_check()

    assert isinstance(response, JSONResponse)
    assert response.status_code == 200
