from __future__ import annotations

import pytest
from agent.tools.asset_lookup import lookup_asset  # type: ignore[import-not-found]
from services.json_eam import JsonEAM  # type: ignore[import-not-found]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lookup_asset_resolves_train_car_subsystem_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.tools import asset_lookup  # type: ignore[import-not-found]

    monkeypatch.setattr(asset_lookup, "get_eam_service", lambda: JsonEAM())

    result = await lookup_asset(query="train car 138 propulsion")

    assert result["found"] is True
    assert result["count"] >= 1
    asset_ids = {item["asset_id"] for item in result["assets"]}
    assert "TC-138-PROP" in asset_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lookup_asset_resolves_spoken_letter_digit_asset_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.tools import asset_lookup  # type: ignore[import-not-found]

    monkeypatch.setattr(asset_lookup, "get_eam_service", lambda: JsonEAM())

    result = await lookup_asset(query="e s c s c 0 0 3")

    assert result["found"] is True
    asset_ids = {item["asset_id"] for item in result["assets"]}
    assert "ESC-SC-003" in asset_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lookup_asset_resolves_vobc_asr_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'TC 229 ovc' should resolve to TC-229-VOBC via ASR correction."""
    from agent.tools import asset_lookup  # type: ignore[import-not-found]

    monkeypatch.setattr(asset_lookup, "get_eam_service", lambda: JsonEAM())

    result = await lookup_asset(query="TC 229 ovc")

    assert result["found"] is True
    asset_ids = {item["asset_id"] for item in result["assets"]}
    assert "TC-229-VOBC" in asset_ids
