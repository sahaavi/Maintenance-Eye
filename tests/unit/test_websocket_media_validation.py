from __future__ import annotations

import asyncio
import base64
import json
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from api import websocket as websocket_module  # type: ignore[import-not-found]
from api.websocket import (  # type: ignore[import-not-found]
    MAX_JPEG_FRAME_BYTES,
    _decode_valid_jpeg_frame,
)

VALID_JPEG_FRAME = b"\xff\xd8" + (b"\x00" * 256) + b"\xff\xd9"


class FakeWebSocket:
    def __init__(self, messages: list[dict[str, Any]]):
        self._messages = [json.dumps(message) for message in messages]
        self.sent_json: list[dict[str, Any]] = []

    async def receive_text(self) -> str:
        return self._messages.pop(0)

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)


class FakeSessionService:
    async def get_session(self, **_: Any) -> object:
        return SimpleNamespace(id="existing-session")

    async def create_session(self, **_: Any) -> object:
        return SimpleNamespace(id="created-session")


class FakeRunner:
    async def run_live(self, **_: Any):
        try:
            while True:
                await asyncio.sleep(1)
                if False:
                    yield SimpleNamespace()
        except asyncio.CancelledError:
            return


@pytest.fixture
def fake_live_queues(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    queues: list[Any] = []

    class FakeLiveRequestQueue:
        def __init__(self) -> None:
            self.realtime: list[Any] = []
            self.content: list[Any] = []
            self.closed = False
            queues.append(self)

        def send_realtime(self, blob: Any) -> None:
            self.realtime.append(blob)

        def send_content(self, content: Any) -> None:
            self.content.append(content)

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(websocket_module, "LiveRequestQueue", FakeLiveRequestQueue)
    monkeypatch.setitem(
        sys.modules,
        "main",
        SimpleNamespace(
            APP_NAME="test-app",
            runner=FakeRunner(),
            session_service=FakeSessionService(),
        ),
    )
    return queues


def test_decode_valid_jpeg_frame_accepts_browser_canvas_jpeg() -> None:
    encoded = _b64(VALID_JPEG_FRAME)

    assert _decode_valid_jpeg_frame(encoded) == VALID_JPEG_FRAME


def test_decode_valid_jpeg_frame_rejects_empty_or_invalid_payloads() -> None:
    assert _decode_valid_jpeg_frame("") is None
    assert _decode_valid_jpeg_frame("not base64!") is None
    assert _decode_valid_jpeg_frame(base64.b64encode(b"").decode("ascii")) is None
    assert _decode_valid_jpeg_frame(base64.b64encode(b"not a jpeg").decode("ascii")) is None
    assert _decode_valid_jpeg_frame(base64.b64encode(b"\xff\xd8\xff\xd9").decode("ascii")) is None
    oversized = b"\xff\xd8" + (b"\x00" * MAX_JPEG_FRAME_BYTES) + b"\xff\xd9"
    assert _decode_valid_jpeg_frame(base64.b64encode(oversized).decode("ascii")) is None


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


async def _run_inspection_messages(
    messages: list[dict[str, Any]],
    queues: list[Any],
) -> tuple[FakeWebSocket, Any]:
    websocket = FakeWebSocket([*messages, {"type": "end_session"}])
    await websocket_module._run_bidi_session(  # type: ignore[attr-defined]
        websocket=websocket,
        resolved_user_id="test-user",
        session_id="test-session-media-validation",
        run_config=SimpleNamespace(),
    )
    return websocket, queues[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "",
        "@@@",
        _b64(b"not a jpeg"),
        _b64(b"\xff\xd8\xff\xd9"),
    ],
)
async def test_inspection_video_drops_invalid_frame_without_client_error(
    fake_live_queues: list[Any],
    payload: str,
) -> None:
    websocket, live_queue = await _run_inspection_messages(
        [{"type": "video", "data": payload}],
        fake_live_queues,
    )

    assert live_queue.realtime == []
    assert [message for message in websocket.sent_json if message["type"] == "error"] == []


@pytest.mark.asyncio
async def test_inspection_image_reports_invalid_payload(fake_live_queues: list[Any]) -> None:
    websocket, live_queue = await _run_inspection_messages(
        [{"type": "image", "data": _b64(b"not a jpeg")}],
        fake_live_queues,
    )

    assert live_queue.realtime == []
    assert {
        "type": "error",
        "data": "Invalid image payload: expected JPEG image data",
    } in websocket.sent_json


@pytest.mark.asyncio
async def test_inspection_video_forwards_valid_jpeg_frame(fake_live_queues: list[Any]) -> None:
    _, live_queue = await _run_inspection_messages(
        [{"type": "video", "data": _b64(VALID_JPEG_FRAME)}],
        fake_live_queues,
    )

    assert len(live_queue.realtime) == 1
    blob = live_queue.realtime[0]
    assert blob.mime_type == "image/jpeg"
    assert blob.data == VALID_JPEG_FRAME
