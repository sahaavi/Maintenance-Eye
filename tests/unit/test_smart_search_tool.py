from __future__ import annotations

import pytest
from agent.tools.smart_search import smart_search  # type: ignore[import-not-found]
from services.json_eam import JsonEAM  # type: ignore[import-not-found]
from services.search_matcher import query_matches_text  # type: ignore[import-not-found]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_suggests_asset_confirmation_for_malformed_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(query="are there any work order for rc 139")

    assert result["success"] is True
    assert result["total"] == 0
    assert result.get("needs_asset_confirmation") is True
    guessed = result.get("guessed_assets", [])
    assert guessed
    assert guessed[0]["asset_id"] == "TC-139"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_reports_no_asset_match_for_unknown_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(query="are there any work order for zz 999")

    assert result["success"] is True
    assert result["total"] == 0
    assert result.get("no_asset_match") is True
    assert result.get("attempted_asset_hints") == ["ZZ-999"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_resolves_vobc_asr_variant_ovc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'tc 229 ovc' should resolve to TC-229-VOBC via ASR corrections."""
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(query="tc 229 ovc")

    assert result["success"] is True
    ids = result["search_metadata"]["extracted_ids"]
    assert "TC-229-VOBC" in ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_resolves_vobc_asr_variant_v_obc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'TC-229 v obc' should resolve to TC-229-VOBC via ASR corrections."""
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(query="TC-229 v obc")

    assert result["success"] is True
    ids = result["search_metadata"]["extracted_ids"]
    assert "TC-229-VOBC" in ids


# --- search_matcher compound-word and fuzzy tests ---


@pytest.mark.unit
def test_query_matches_text_compound_word() -> None:
    """'metro town' should match 'metrotown' via compound-word matching."""
    assert query_matches_text(
        "metro town track circuit 3",
        "Metrotown Track Circuit #3 signal_telecom TRC-MT-003",
    )


@pytest.mark.unit
def test_query_matches_text_strips_id_noise() -> None:
    """'id' should be noise and not block matching."""
    assert query_matches_text(
        "asset id metrotown track circuit 3",
        "Metrotown Track Circuit #3 signal_telecom TRC-MT-003",
    )


@pytest.mark.unit
def test_query_matches_text_fuzzy_asr_error() -> None:
    """'downtrex' should fuzzy-match 'downtown' via bigram similarity."""
    assert query_matches_text(
        "downtrex circuit 3",
        "Downtown Track Circuit #3 signal_telecom TRC-DT-003",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_finds_track_circuit_wo_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Natural query for Metrotown Track Circuit 3 should find WO-2025-0006."""
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(query="Is there any open work order for Metrotown Track Circuit 3?")

    assert result["success"] is True
    assert result["total"] > 0
    wo_ids = [
        r["data"]["wo_id"] for r in result.get("results", []) if r.get("data", {}).get("wo_id")
    ]
    assert "WO-2025-0006" in wo_ids
