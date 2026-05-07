from __future__ import annotations

from types import SimpleNamespace

from api.websocket import _transcription_messages_for_event  # type: ignore[import-not-found]


def test_live_event_transcription_fields_are_forwarded_to_client() -> None:
    event = SimpleNamespace(
        input_transcription=SimpleNamespace(text="show me the panel", finished=False),
        output_transcription=SimpleNamespace(text="I see the panel clearly.", finished=False),
    )

    assert _transcription_messages_for_event(event) == [
        {"type": "transcript_input", "data": "show me the panel"},
        {"type": "transcript_output", "data": "I see the panel clearly."},
    ]


def test_live_event_transcription_fields_ignore_empty_text() -> None:
    event = SimpleNamespace(
        input_transcription=SimpleNamespace(text=" ", finished=False),
        output_transcription=None,
    )

    assert _transcription_messages_for_event(event) == []
