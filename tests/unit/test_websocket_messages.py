from __future__ import annotations

from typing import Any

import pytest
from models.websocket_messages import (
    audio_message,
    confirmation_request_message,
    confirmation_result_message,
    error_message,
    media_card_message,
    session_summary_message,
    status_message,
    text_message,
    transcript_input_message,
    transcript_output_message,
    turn_complete_message,
    work_order_message,
)
from pydantic import ValidationError


def test_status_message_preserves_optional_session_id_wire_shape() -> None:
    assert status_message("Connected", session_id="inspect-123") == {
        "type": "status",
        "data": "Connected",
        "session_id": "inspect-123",
    }
    assert status_message("Online") == {"type": "status", "data": "Online"}


def test_audio_and_transcript_messages_preserve_wire_shape() -> None:
    assert audio_message("YWJj", mime_type="audio/pcm;rate=24000") == {
        "type": "audio",
        "data": "YWJj",
        "mime_type": "audio/pcm;rate=24000",
    }
    assert transcript_input_message("hello") == {"type": "transcript_input", "data": "hello"}
    assert transcript_output_message("done") == {"type": "transcript_output", "data": "done"}
    assert text_message("chat response") == {"type": "text", "data": "chat response"}


def test_confirmation_messages_preserve_nested_payloads() -> None:
    request_payload = {
        "action_id": "ACT-001",
        "confirmation_prompt": {"message": "Create work order?"},
    }
    execution = {"success": True, "work_order": {"wo_id": "WO-001"}}

    assert confirmation_request_message(request_payload) == {
        "type": "confirmation_request",
        "data": request_payload,
    }
    assert confirmation_result_message(
        action_id="ACT-001",
        status="corrected",
        execution=execution,
        corrected_data={"priority": "P2"},
    ) == {
        "type": "confirmation_result",
        "data": {
            "action_id": "ACT-001",
            "status": "corrected",
            "corrected_data": {"priority": "P2"},
            "execution": execution,
        },
    }


def test_work_order_media_summary_turn_and_error_messages_preserve_wire_shape() -> None:
    work_order = {"wo_id": "WO-001", "description": "Replace relay"}
    media_card = {
        "title": "Asset: Switch",
        "description": None,
        "image_url": "https://example.test/switch.svg",
        "action_label": "Open Report",
        "details": [{"label": "Asset ID", "value": "AST-001"}],
    }

    assert work_order_message(work_order) == {"type": "work_order", "data": work_order}
    assert media_card_message(media_card) == {"type": "media_card", "data": media_card}
    assert session_summary_message(
        session_id="inspect-123",
        findings_count=2,
        confirmation_stats={"confirmed": 1},
    ) == {
        "type": "session_summary",
        "data": {
            "session_id": "inspect-123",
            "findings_count": 2,
            "confirmation_stats": {"confirmed": 1},
        },
    }
    assert turn_complete_message() == {"type": "turn_complete", "data": ""}
    assert error_message("Live API error") == {"type": "error", "data": "Live API error"}


def test_confirmation_result_rejects_unknown_status() -> None:
    queued_status: Any = "queued"
    with pytest.raises(ValidationError):
        confirmation_result_message(action_id="ACT-001", status=queued_status)
