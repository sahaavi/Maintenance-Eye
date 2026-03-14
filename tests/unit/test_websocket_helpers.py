from __future__ import annotations

import pytest
from api.websocket import (  # type: ignore[import-not-found]
    _decode_additional_data,
    _execute_confirmed_action,
    _extract_confirmation_request,
    _extract_media_cards,
)
from services.confirmation_manager import (  # type: ignore[import-not-found]
    ActionType,
    PendingAction,
)


def test_extract_confirmation_request_finds_nested_payload() -> None:
    payload = {
        "wrapper": {
            "result": {
                "action_id": "ACT-001",
                "confirmation_prompt": {"message": "confirm?"},
            }
        }
    }

    extracted = _extract_confirmation_request(payload)
    assert extracted is not None
    assert extracted["action_id"] == "ACT-001"


def test_decode_additional_data_parses_json_or_returns_empty() -> None:
    parsed = _decode_additional_data('{"priority": "P2"}')
    assert parsed == {"priority": "P2"}
    assert _decode_additional_data("not-json") == {}


def test_extract_media_cards_supports_asset_and_kb_shapes() -> None:
    payload = [
        {
            "title": "Procedure",
            "content": "Step by step instructions",
            "asset_types": ["signal"],
        },
        {
            "asset_id": "AST-001",
            "name": "Switch",
            "type": "guideway",
            "status": "operational",
        },
    ]

    cards = _extract_media_cards(payload)
    assert len(cards) == 2
    assert cards[0]["title"] == "Procedure"
    assert cards[1]["title"].startswith("Asset:")


def test_extract_media_cards_supports_work_order_and_zero_result_summary() -> None:
    payload = {
        "intent": "work_order",
        "total": 0,
        "results": [],
        "search_metadata": {"raw_input": "open wo for train car 138 propulsion"},
        "extra": {
            "wo_id": "WO-2026-0166",
            "asset_id": "TC-138-PROP",
            "status": "open",
            "priority": "P2",
            "description": "Propulsion PCU fault",
        },
    }

    cards = _extract_media_cards(payload)
    assert len(cards) == 2
    assert cards[0]["title"] == "No Matching Records"
    assert cards[1]["title"] == "Work Order: WO-2026-0166"


@pytest.mark.asyncio
async def test_execute_confirmed_create_requires_asset_id() -> None:
    action = PendingAction(
        action_type=ActionType.CREATE_WORK_ORDER,
        session_id="ws-test-session-asset",
        asset_id="",
        description="Create work order for vibration",
        proposed_data={},
        ai_confidence=0.8,
    )

    result = await _execute_confirmed_action(action)
    assert result["success"] is False
    assert result.get("missing_fields") == ["asset_id"]


@pytest.mark.asyncio
async def test_execute_confirmed_create_requires_description() -> None:
    action = PendingAction(
        action_type=ActionType.CREATE_WORK_ORDER,
        session_id="ws-test-session-description",
        asset_id="AST-UNIT-001",
        description="",
        proposed_data={"asset_id": "AST-UNIT-001"},
        ai_confidence=0.8,
    )

    result = await _execute_confirmed_action(action)
    assert result["success"] is False
    assert result.get("missing_fields") == ["description"]
