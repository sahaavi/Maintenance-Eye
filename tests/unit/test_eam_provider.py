from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def reset_eam_provider():
    from services import eam_provider  # type: ignore[import-not-found]

    eam_provider._eam_service = None
    yield
    eam_provider._eam_service = None


@pytest.mark.unit
def test_provider_falls_back_to_json_eam_when_firestore_runtime_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import eam_provider  # type: ignore[import-not-found]
    from services.json_eam import JsonEAM  # type: ignore[import-not-found]

    monkeypatch.setattr(eam_provider, "_has_firestore_runtime", lambda: False)

    eam = eam_provider.get_eam_service()

    assert isinstance(eam, JsonEAM)


@pytest.mark.unit
def test_provider_caches_fallback_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import eam_provider  # type: ignore[import-not-found]

    created = []

    class FakeJsonEAM:
        def __init__(self) -> None:
            created.append(self)

    monkeypatch.setattr(eam_provider, "_has_firestore_runtime", lambda: False)
    monkeypatch.setattr(eam_provider, "JsonEAM", FakeJsonEAM)

    first = eam_provider.get_eam_service()
    second = eam_provider.get_eam_service()

    assert first is second
    assert len(created) == 1


@pytest.mark.unit
def test_provider_falls_back_to_json_eam_when_firestore_init_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import eam_provider  # type: ignore[import-not-found]

    class BrokenFirestoreEAM:
        def __init__(self) -> None:
            raise RuntimeError("credentials revoked")

    class FakeJsonEAM:
        pass

    monkeypatch.setattr(eam_provider, "_has_firestore_runtime", lambda: True)
    monkeypatch.setattr(eam_provider, "FirestoreEAM", BrokenFirestoreEAM)
    monkeypatch.setattr(eam_provider, "JsonEAM", FakeJsonEAM)

    eam = eam_provider.get_eam_service()

    assert isinstance(eam, FakeJsonEAM)


@pytest.mark.unit
def test_firestore_runtime_requires_refreshable_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.auth.exceptions import RefreshError
    from services import eam_provider  # type: ignore[import-not-found]

    class StaleCredentials:
        valid = False

        def refresh(self, request) -> None:
            raise RefreshError("invalid_grant")

    monkeypatch.setattr(eam_provider.settings, "FIRESTORE_EMULATOR_HOST", "")
    monkeypatch.setattr(
        eam_provider.google.auth,
        "default",
        lambda scopes=None: (StaleCredentials(), "maintenance-eye"),
    )
    monkeypatch.setattr(eam_provider, "Request", lambda: object())

    assert eam_provider._has_firestore_runtime() is False
