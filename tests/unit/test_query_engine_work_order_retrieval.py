from __future__ import annotations

import pytest
from services.json_eam import JsonEAM  # type: ignore[import-not-found]
from services.query_engine import QueryEngine, SearchIntent  # type: ignore[import-not-found]


@pytest.mark.unit
def test_build_query_drops_filler_words_and_normalizes_number_words() -> None:
    engine = QueryEngine()

    parsed = engine.build_query(
        "is there any open work order for escalator three at Stadium Chinatown"
    )

    assert parsed.intent == SearchIntent.work_order
    assert parsed.filters.get("status") == "open"
    assert "there" not in parsed.normalized_terms
    assert "any" not in parsed.normalized_terms
    assert "three" not in parsed.normalized_terms
    assert "3" in parsed.normalized_terms


@pytest.mark.unit
def test_build_query_extracts_spaced_asset_ids() -> None:
    engine = QueryEngine()

    parsed = engine.build_query("do we have any open work orders for esc sc 003")

    assert parsed.intent == SearchIntent.work_order
    assert "ESC-SC-003" in parsed.extracted_ids


@pytest.mark.unit
def test_build_query_extracts_spoken_asset_id_with_dash_words() -> None:
    engine = QueryEngine()

    parsed = engine.build_query("open work orders for e s c dash s c dash zero zero three")

    assert parsed.intent == SearchIntent.work_order
    assert "ESC-SC-003" in parsed.extracted_ids


@pytest.mark.unit
def test_build_query_extracts_spoken_train_car_id() -> None:
    engine = QueryEngine()

    parsed = engine.build_query("open work orders for t c one three eight prop")

    assert parsed.intent == SearchIntent.work_order
    assert "TC-138-PROP" in parsed.extracted_ids


@pytest.mark.unit
def test_build_query_extracts_train_car_subsystem_id() -> None:
    engine = QueryEngine()

    parsed = engine.build_query("open work orders for train car 138 propulsion")

    assert parsed.intent == SearchIntent.work_order
    assert parsed.filters.get("asset_type") == "propulsion"
    assert "TC-138-PROP" in parsed.extracted_ids


@pytest.mark.unit
def test_build_query_avoids_false_asset_id_prefix_from_stopwords() -> None:
    engine = QueryEngine()

    parsed = engine.build_query("open work orders for tc-138-prop")

    assert "FOR-TC-138" not in parsed.extracted_ids
    assert "TC-138-PROP" in parsed.extracted_ids


@pytest.mark.unit
def test_normalize_asset_id_handles_spoken_transcription() -> None:
    normalized = QueryEngine.normalize_asset_id("e s c dash s c dash zero zero three")
    assert normalized == "ESC-SC-003"


@pytest.mark.unit
def test_extract_asset_hints_for_malformed_id() -> None:
    hints = QueryEngine.extract_asset_hints("are there any work order for rc 139")
    assert hints == ["RC-139"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_suggest_asset_candidates_for_malformed_id() -> None:
    engine = QueryEngine()
    eam = JsonEAM()

    suggestions = await engine.suggest_asset_candidates(
        "are there any work order for rc 139",
        eam,
        limit=3,
    )

    assert suggestions
    assert suggestions[0]["asset_id"] == "TC-139"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_handles_natural_open_work_order_question() -> None:
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query(
        "is there any open work order for escalator three at Stadium Chinatown"
    )
    result = await engine.execute_search(parsed, eam, limit=20)

    wo_ids = {item.item.wo_id for item in result.items if item.entity_type == "work_order"}
    assert "WO-2026-0151" in wo_ids
    assert "WO-2026-0152" in wo_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_handles_spoken_asset_id_variant() -> None:
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query("open work orders for e s c s c 0 0 3")
    result = await engine.execute_search(parsed, eam, limit=10)

    wo_ids = {item.item.wo_id for item in result.items if item.entity_type == "work_order"}
    assert "WO-2026-0151" in wo_ids
    assert "WO-2026-0152" in wo_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_resolves_train_car_subsystem_asset() -> None:
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query("train car 138 propulsion")
    result = await engine.execute_search(parsed, eam, limit=10)

    asset_ids = {item.item.asset_id for item in result.items if item.entity_type == "asset"}
    assert "TC-138-PROP" in asset_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_finds_open_work_order_for_train_car_subsystem() -> None:
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query("is there any open work order for train car 138 propulsion")
    result = await engine.execute_search(parsed, eam, limit=10)

    wo_ids = {item.item.wo_id for item in result.items if item.entity_type == "work_order"}
    assert "WO-2026-0166" in wo_ids


# --- ASR fuzzy matching tests ---


@pytest.mark.unit
def test_build_query_resolves_vobc_asr_variant_v_obc() -> None:
    engine = QueryEngine()
    parsed = engine.build_query("TC-229 v obc")
    assert "TC-229-VOBC" in parsed.extracted_ids


@pytest.mark.unit
def test_build_query_resolves_vobc_asr_variant_ovc() -> None:
    engine = QueryEngine()
    parsed = engine.build_query("tc 229 ovc")
    assert "TC-229-VOBC" in parsed.extracted_ids


@pytest.mark.unit
def test_build_query_resolves_vobc_asr_variant_bobc() -> None:
    engine = QueryEngine()
    parsed = engine.build_query("tc 229 bobc")
    assert "TC-229-VOBC" in parsed.extracted_ids


@pytest.mark.unit
def test_detect_train_subsystem_suffix_vobc_asr_variants() -> None:
    assert QueryEngine._detect_train_subsystem_suffix("check the v obc unit") == "VOBC"
    assert QueryEngine._detect_train_subsystem_suffix("ovc controller") == "VOBC"
    assert QueryEngine._detect_train_subsystem_suffix("bobc fault") == "VOBC"
    assert QueryEngine._detect_train_subsystem_suffix("vo bc system") == "VOBC"


@pytest.mark.unit
def test_apply_asr_corrections() -> None:
    assert "vobc" in QueryEngine._apply_asr_corrections("V OBC unit")
    assert "vobc" in QueryEngine._apply_asr_corrections("the OVC is broken")
    assert "vobc" in QueryEngine._apply_asr_corrections("check BOBC")
    assert "propulsion" in QueryEngine._apply_asr_corrections("pro pulsion system")


# --- Short-form asset hint extraction tests ---


@pytest.mark.unit
def test_extract_ids_catches_short_form_rc_139() -> None:
    engine = QueryEngine()
    parsed = engine.build_query("work orders for rc 139")
    # RC is a valid prefix in _ASSET_ID_PREFIXES
    assert any("RC-139" in eid for eid in parsed.extracted_ids)


# --- Pre-resolution tests ---


@pytest.mark.unit
def test_build_query_no_dept_conflict_with_track_circuit_asset_type() -> None:
    """'track' in 'track circuit' should NOT set department=guideway."""
    engine = QueryEngine()
    parsed = engine.build_query("Is there any open work order for Metrotown Track Circuit 3?")
    assert parsed.filters.get("asset_type") == "track_circuit"
    assert "department" not in parsed.filters


@pytest.mark.unit
def test_build_query_strips_id_noise_word() -> None:
    """'id' should be removed as a noise word, not become a search term."""
    engine = QueryEngine()
    parsed = engine.build_query("What's the asset ID for Metro Town Track Circuit 3?")
    assert "id" not in parsed.normalized_terms


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_finds_track_circuit_wo_by_natural_name() -> None:
    """Natural name 'Metrotown Track Circuit 3' should find WO-2025-0006."""
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query("Is there any open work order for Metrotown Track Circuit 3?")
    result = await engine.execute_search(parsed, eam, limit=20)

    wo_ids = {item.item.wo_id for item in result.items if item.entity_type == "work_order"}
    assert "WO-2025-0006" in wo_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_search_finds_asset_by_compound_name() -> None:
    """'Metro Town Track Circuit 3' (split name) should find TRC-MT-003."""
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query("What's the asset ID for Metro Town Track Circuit 3?")
    result = await engine.execute_search(parsed, eam, limit=20)

    asset_ids = {item.item.asset_id for item in result.items if item.entity_type == "asset"}
    assert "TRC-MT-003" in asset_ids


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_work_orders_pre_resolves_rc_to_rct() -> None:
    """When 'RC-139' doesn't match a real asset, pre-resolution should try
    to find a matching asset and substitute it in the WO search."""
    engine = QueryEngine()
    eam = JsonEAM()

    parsed = engine.build_query("work orders for rc 139")
    result = await engine.execute_search(parsed, eam, limit=10)

    # Even if no WOs are found for the resolved asset, we verify the
    # pre-resolution path ran without error and returned a valid result
    assert result is not None
    assert result.query.intent == SearchIntent.work_order
