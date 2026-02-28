"""
WebSocket Handler — ADK Bidi-Streaming
Real-time bidirectional audio/video/text streaming between the phone client
and the Gemini Live API via ADK Runner.

Architecture:
  Phone (mic + camera) → WebSocket → LiveRequestQueue → ADK Runner → Gemini Live API
                       ←           ← run_live() events ←             ←

Supports:
  - Audio streaming (PCM 16kHz → agent → PCM 24kHz)
  - Video frames (JPEG from phone camera)
  - Text messages
  - Human-in-the-loop confirmation flow
  - Barge-in / interruption (handled natively by Live API)
"""

import asyncio
import traceback
import base64
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.genai import types

from services.confirmation_manager import (
    get_confirmation_manager,
    remove_confirmation_manager,
)
from agent.tools.confirm_action import set_session_context

router = APIRouter()
logger = logging.getLogger("maintenance-eye.websocket")

# Audio configuration
SEND_SAMPLE_RATE = 16000   # Phone → server (PCM 16kHz mono 16-bit)
RECEIVE_SAMPLE_RATE = 24000  # Server → phone (PCM 24kHz mono 16-bit)


class InspectionSession:
    """
    Manages a single live inspection session.
    Bridges the phone client → LiveRequestQueue → ADK Runner → Gemini Live API.
    """

    def __init__(self, session_id: str, user_id: str, websocket: WebSocket):
        self.session_id = session_id
        self.user_id = user_id
        self.websocket = websocket
        self.is_active = True
        self.current_asset_id: Optional[str] = None
        self.findings: list[dict] = []

    async def close(self):
        self.is_active = False


# Active sessions
active_sessions: dict[str, InspectionSession] = {}


@router.websocket("/ws/inspect/{user_id}")
@router.websocket("/ws/inspect/{user_id}/{session_id}")
async def inspection_websocket(
    websocket: WebSocket,
    user_id: str,
    session_id: str = "",
) -> None:
    """
    WebSocket endpoint for live inspection sessions with ADK bidi-streaming.

    Client sends:
    - {"type": "audio", "data": "<base64 PCM audio>"}
    - {"type": "video", "data": "<base64 JPEG frame>"}
    - {"type": "text", "data": "user text message"}
    - {"type": "start_session", "asset_id": "optional"}
    - {"type": "end_session"}
    - {"type": "confirm", "action_id": "<id>", "notes": "optional"}
    - {"type": "reject", "action_id": "<id>", "notes": "optional"}
    - {"type": "correct", "action_id": "<id>", "corrections": {...}}

    Server sends:
    - {"type": "audio", "data": "<base64 PCM audio>"}
    - {"type": "text", "data": "agent text response"}
    - {"type": "transcript_input", "data": "what user said"}
    - {"type": "transcript_output", "data": "what agent said"}
    - {"type": "tool_call", "data": {tool name + args}}
    - {"type": "tool_result", "data": {tool result}}
    - {"type": "confirmation_request", "data": {pending action}}
    - {"type": "confirmation_result", "data": {result}}
    - {"type": "status", "data": "session status message"}
    """
    await websocket.accept()

    # Import runner from main module (avoid circular import)
    from main import runner, session_service, APP_NAME

    # Generate session ID if not provided
    if not session_id:
        session_id = f"inspect-{id(websocket)}"

    session = InspectionSession(session_id, user_id, websocket)
    active_sessions[session_id] = session

    # Set session context for confirmation tools
    set_session_context(session_id)
    confirmation_mgr = get_confirmation_manager(session_id)

    logger.info(f"New inspection session: {session_id} (user: {user_id})")

    # ====================================================================
    # Phase 2: Session Initialization
    # ====================================================================

    # Configure bidi-streaming with audio + text response
    run_config = RunConfig(
        streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )

    # Get or create ADK session
    adk_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    if not adk_session:
        adk_session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

    # Create LiveRequestQueue for this session
    live_request_queue = LiveRequestQueue()

    await websocket.send_json({
        "type": "status",
        "data": "Connected to Maintenance-Eye. Live API ready.",
        "session_id": session_id,
    })

    # ====================================================================
    # Phase 3: Bidi-streaming — concurrent upstream + downstream
    # ====================================================================

    async def upstream_task() -> None:
        """
        Receives messages from WebSocket client and routes them:
        - audio/video → LiveRequestQueue.send_realtime()
        - text → LiveRequestQueue.send_content()
        - confirmation messages → ConfirmationManager
        """
        try:
            while session.is_active:
                raw = await websocket.receive_text()
                message = json.loads(raw)
                msg_type = message.get("type", "")

                if msg_type == "end_session":
                    logger.info(f"Session ended by client: {session_id}")
                    session.is_active = False
                    break

                elif msg_type == "start_session":
                    session.current_asset_id = message.get("asset_id", "")
                    # Send asset context as text to the agent
                    if session.current_asset_id:
                        content = types.Content(
                            parts=[types.Part(
                                text=f"The technician is now inspecting asset: {session.current_asset_id}"
                            )]
                        )
                        live_request_queue.send_content(content)

                elif msg_type == "audio":
                    # Decode base64 PCM audio and send to Live API
                    audio_data = base64.b64decode(message["data"])
                    audio_blob = types.Blob(
                        mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}",
                        data=audio_data,
                    )
                    live_request_queue.send_realtime(audio=audio_blob)

                elif msg_type == "video":
                    # Decode base64 JPEG frame and send to Live API
                    frame_data = base64.b64decode(message["data"])
                    video_blob = types.Blob(
                        mime_type="image/jpeg",
                        data=frame_data,
                    )
                    live_request_queue.send_realtime(video=video_blob)

                elif msg_type == "text":
                    # Send text message to agent
                    content = types.Content(
                        parts=[types.Part(text=message["data"])]
                    )
                    live_request_queue.send_content(content)

                # -----------------------------------------------------------
                # Human-in-the-Loop: confirmation responses
                # -----------------------------------------------------------
                elif msg_type == "confirm":
                    action_id = message.get("action_id", "")
                    notes = message.get("notes", "")
                    action = confirmation_mgr.confirm(action_id, notes)
                    if action:
                        # Tell the agent about the confirmation via text
                        content = types.Content(
                            parts=[types.Part(
                                text=f"The technician CONFIRMED action {action_id}. "
                                     f"Proceed with: {action.description}"
                            )]
                        )
                        live_request_queue.send_content(content)
                        await websocket.send_json({
                            "type": "confirmation_result",
                            "data": {
                                "action_id": action_id,
                                "status": "confirmed",
                            },
                        })

                elif msg_type == "reject":
                    action_id = message.get("action_id", "")
                    notes = message.get("notes", "")
                    action = confirmation_mgr.reject(action_id, notes)
                    if action:
                        content = types.Content(
                            parts=[types.Part(
                                text=f"The technician REJECTED action {action_id}. "
                                     f"Reason: {notes or 'No reason given'}. "
                                     f"Ask if they want a different approach."
                            )]
                        )
                        live_request_queue.send_content(content)
                        await websocket.send_json({
                            "type": "confirmation_result",
                            "data": {
                                "action_id": action_id,
                                "status": "rejected",
                            },
                        })

                elif msg_type == "correct":
                    action_id = message.get("action_id", "")
                    corrections = message.get("corrections", {})
                    notes = message.get("notes", "")
                    action = confirmation_mgr.correct(action_id, corrections, notes)
                    if action:
                        content = types.Content(
                            parts=[types.Part(
                                text=f"The technician CORRECTED action {action_id}. "
                                     f"Updated values: {json.dumps(corrections)}. "
                                     f"Use these corrected values."
                            )]
                        )
                        live_request_queue.send_content(content)
                        await websocket.send_json({
                            "type": "confirmation_result",
                            "data": {
                                "action_id": action_id,
                                "status": "corrected",
                                "corrected_data": action.proposed_data,
                            },
                        })

                else:
                    logger.warning(f"Unknown message type: {msg_type}")

        except WebSocketDisconnect:
            logger.info(f"Client disconnected (upstream): {session_id}")
        except Exception as e:
            logger.error(f"Upstream error: {session_id} — {e}\n{traceback.format_exc()}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": f"Upstream error: {str(e)}",
                })
            except Exception:
                pass

    async def downstream_task() -> None:
        """
        Receives events from ADK run_live() and routes them to the WebSocket.
        Events include: audio chunks, text, transcriptions, tool calls, etc.
        """
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=run_config,
            ):
                if not session.is_active:
                    break

                # --- Audio response from agent ---
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        # Audio data
                        if part.inline_data and part.inline_data.data:
                            audio_b64 = base64.b64encode(
                                part.inline_data.data
                            ).decode("utf-8")
                            await websocket.send_json({
                                "type": "audio",
                                "data": audio_b64,
                                "mime_type": part.inline_data.mime_type or f"audio/pcm;rate={RECEIVE_SAMPLE_RATE}",
                            })

                        # Text response
                        elif part.text:
                            await websocket.send_json({
                                "type": "text",
                                "data": part.text,
                            })

                # --- Transcription of user's speech (input) ---
                if hasattr(event, "input_transcription") and event.input_transcription:
                    await websocket.send_json({
                        "type": "transcript_input",
                        "data": event.input_transcription,
                    })

                # --- Transcription of agent's speech (output) ---
                if hasattr(event, "output_transcription") and event.output_transcription:
                    await websocket.send_json({
                        "type": "transcript_output",
                        "data": event.output_transcription,
                    })

                # --- Tool calls and results ---
                if hasattr(event, "actions") and event.actions:
                    if event.actions.tool_code_execution_result:
                        await websocket.send_json({
                            "type": "tool_result",
                            "data": str(event.actions.tool_code_execution_result),
                        })

                # --- Interruption (barge-in) ---
                if event.interrupted:
                    await websocket.send_json({
                        "type": "interrupted",
                        "data": "Agent interrupted by user input",
                    })

        except WebSocketDisconnect:
            logger.info(f"Client disconnected (downstream): {session_id}")
        except Exception as e:
            logger.error(f"Downstream error: {session_id} — {e}\n{traceback.format_exc()}")
            try:
                await websocket.send_json({
                    "type": "error",
                    "data": f"Live API error: {str(e)}",
                })
            except Exception:
                pass

    # Run upstream and downstream concurrently
    try:
        await asyncio.gather(
            upstream_task(),
            downstream_task(),
            return_exceptions=True,
        )
    finally:
        # ================================================================
        # Phase 4: Session Termination
        # ================================================================
        live_request_queue.close()
        session.is_active = False
        active_sessions.pop(session_id, None)
        stats = remove_confirmation_manager(session_id)

        try:
            await websocket.send_json({
                "type": "session_summary",
                "data": {
                    "session_id": session_id,
                    "findings_count": len(session.findings),
                    "confirmation_stats": stats or {},
                },
            })
        except Exception:
            pass  # Client may already be disconnected

        logger.info(f"Session terminated: {session_id} — stats: {stats}")
