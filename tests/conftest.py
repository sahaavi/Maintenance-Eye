from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.routes import router as api_router  # type: ignore[import-not-found]

from tests.fixtures.factories import FakeEAM


@pytest.fixture(autouse=True)
def _test_env_defaults(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("APP_ENV", os.getenv("APP_ENV", "testing"))
    monkeypatch.setenv("ENABLE_AUTH", "false")
    monkeypatch.setenv("GCS_BUCKET", "")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "")
    yield


@pytest.fixture
def fake_eam() -> FakeEAM:
    return FakeEAM()


@pytest.fixture
def json_eam():
    """Provide a JsonEAM instance backed by seed_data.json."""
    from services.json_eam import JsonEAM  # type: ignore[import-not-found]

    return JsonEAM()


@pytest.fixture
def patch_eam(monkeypatch: pytest.MonkeyPatch, fake_eam: FakeEAM):
    """Monkeypatch get_eam_service in a given module to return fake_eam.
    Returns a callable: patch_eam(module) patches that module's get_eam_service.
    """

    def _patch(module):
        monkeypatch.setattr(module, "get_eam_service", lambda: fake_eam)

    return _patch


@pytest.fixture
def api_app(monkeypatch: pytest.MonkeyPatch, fake_eam: FakeEAM) -> FastAPI:
    from services import firestore_eam  # type: ignore[import-not-found]

    monkeypatch.setattr(firestore_eam, "_eam_service", fake_eam, raising=False)
    monkeypatch.setattr(firestore_eam, "get_eam_service", lambda: fake_eam, raising=True)

    app = FastAPI(title="maintenance-eye-tests")
    app.include_router(api_router, prefix="/api")
    return app


@pytest.fixture
def client(api_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(api_app) as test_client:
        yield test_client
