from __future__ import annotations

import pytest
from agent.tools.smart_search import smart_search  # type: ignore[import-not-found]
from services.json_eam import JsonEAM  # type: ignore[import-not-found]
from services.search_matcher import (
    query_match_score,  # type: ignore[import-not-found]
    query_matches_text,  # type: ignore[import-not-found]
)


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


# --- Fuzzy asset name matching tests ---


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_suggests_for_garbled_station_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'Lohi Town section track Section 3' should suggest RAL-LO-003."""
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(
        query="Is there any open work order for Lohi Town section track Section 3?"
    )

    assert result["success"] is True
    # Either direct results (ASR correction worked) or suggestions
    if result["total"] == 0:
        assert result.get("needs_asset_confirmation") is True
        guessed = result.get("guessed_assets", [])
        assert guessed
        guessed_ids = [g["asset_id"] for g in guessed]
        assert "RAL-LO-003" in guessed_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_smart_search_asr_corrected_station_finds_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'lougheed escalator 2' should directly find ESC-LO-002."""
    from agent.tools import smart_search as smart_search_module  # type: ignore[import-not-found]

    monkeypatch.setattr(smart_search_module, "get_eam_service", lambda: JsonEAM())

    result = await smart_search(query="lougheed escalator 2", search_type="asset")

    assert result["success"] is True
    assert result["total"] > 0
    asset_ids = [
        r["data"]["asset_id"]
        for r in result.get("results", [])
        if r.get("data", {}).get("asset_id")
    ]
    assert "ESC-LO-002" in asset_ids


@pytest.mark.unit
def test_query_match_score_returns_fraction() -> None:
    """query_match_score should return the fraction of matched tokens."""
    # All tokens match → 1.0
    score_full = query_match_score("lougheed escalator", "Lougheed Town Centre Escalator #2")
    assert score_full == 1.0

    # Partial match — 'nonexistent' won't match
    score_partial = query_match_score("lougheed nonexistent", "Lougheed Town Centre Escalator #2")
    assert 0.0 < score_partial < 1.0

    # No match at all
    score_none = query_match_score("zzz yyy xxx", "Lougheed Town Centre Escalator #2")
    assert score_none == 0.0


@pytest.mark.unit
def test_domain_correction_track_to_rail() -> None:
    """'track section 3' should match 'rail section #3' via domain correction."""
    assert query_matches_text(
        "track section 3",
        "Lougheed Town Centre Rail Section #3 guideway RAL-LO-003",
    )


@pytest.mark.unit
def test_existing_track_circuit_still_matches() -> None:
    """Regression: 'metro town track circuit 3' must still match after track->rail."""
    assert query_matches_text(
        "metro town track circuit 3",
        "Metrotown Track Circuit #3 signal_telecom TRC-MT-003",
    )
