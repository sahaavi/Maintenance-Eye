import logging
from typing import Any

from api.websocket import _execute_confirmed_action, _upload_work_order_artifact
from fastapi import WebSocket
from google.genai import types
from services.confirmation_manager import ConfirmationManager

logger = logging.getLogger("maintenance-eye.websocket.helpers")


async def handle_confirmation_message(
    msg_type: str,
    payload: dict,
    message: dict,
    confirmation_mgr: ConfirmationManager,
    session_id: str,
    live_request_queue: Any,
    websocket: WebSocket,
) -> None:
    """Shared handler for Human-in-the-Loop confirmation messages."""
    action_id = payload.get("action_id") or message.get("action_id", "")
    notes = payload.get("notes") or message.get("notes", "")

    if msg_type == "confirm":
        action = confirmation_mgr.confirm(action_id, notes)
        if action:
            execution = await _execute_confirmed_action(action)
            wo_id = ""
            if execution.get("success") and execution.get("work_order"):
                wo_id = execution["work_order"].get("wo_id", "")

            if live_request_queue:
                content = types.Content(
                    parts=[
                        types.Part(
                            text=f"[SYSTEM] Action {action_id} was CONFIRMED and ALREADY EXECUTED by the system. "
                            f"{'Work order ' + wo_id + ' was created. ' if wo_id else ''}"
                            f"Do NOT call manage_work_order again — the action is complete. "
                            f"Just acknowledge the result to the technician briefly."
                        )
                    ]
                )
                live_request_queue.send_content(content)

            await websocket.send_json(
                {
                    "type": "confirmation_result",
                    "data": {
                        "action_id": action_id,
                        "status": "confirmed",
                        "execution": execution,
                    },
                }
            )
            if execution.get("success") and execution.get("work_order"):
                artifact_uri = await _upload_work_order_artifact(
                    session_id=session_id,
                    action_id=action_id,
                    execution_result=execution,
                )
                if artifact_uri:
                    logger.debug(f"Stored work-order artifact: {artifact_uri}")
                await websocket.send_json(
                    {
                        "type": "work_order",
                        "data": execution.get("work_order"),
                    }
                )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "data": f"Unknown action_id: {action_id}",
                }
            )

    elif msg_type == "reject":
        action = confirmation_mgr.reject(action_id, notes)
        if action:
            if live_request_queue:
                content = types.Content(
                    parts=[
                        types.Part(
                            text=f"[SYSTEM] The technician REJECTED action {action_id}. "
                            f"Reason: {notes or 'No reason given'}. "
                            f"Acknowledge briefly and ask if they want a different approach."
                        )
                    ]
                )
                live_request_queue.send_content(content)
            await websocket.send_json(
                {
                    "type": "confirmation_result",
                    "data": {
                        "action_id": action_id,
                        "status": "rejected",
                    },
                }
            )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "data": f"Unknown action_id: {action_id}",
                }
            )

    elif msg_type == "correct":
        corrections = payload.get("corrections")
        if not isinstance(corrections, dict):
            corrections = message.get("corrections", {})
        if not isinstance(corrections, dict):
            corrections = {}

        action = confirmation_mgr.correct(action_id, corrections, notes)
        if action:
            execution = await _execute_confirmed_action(action)
            wo_id = ""
            if execution.get("success") and execution.get("work_order"):
                wo_id = execution["work_order"].get("wo_id", "")

            if live_request_queue:
                content = types.Content(
                    parts=[
                        types.Part(
                            text=f"[SYSTEM] Action {action_id} was CORRECTED and ALREADY EXECUTED with updated values. "
                            f"{'Work order ' + wo_id + ' was created. ' if wo_id else ''}"
                            f"Do NOT call manage_work_order again. Just acknowledge briefly."
                        )
                    ]
                )
                live_request_queue.send_content(content)

            await websocket.send_json(
                {
                    "type": "confirmation_result",
                    "data": {
                        "action_id": action_id,
                        "status": "corrected",
                        "corrected_data": action.proposed_data,
                        "execution": execution,
                    },
                }
            )
            if execution.get("success") and execution.get("work_order"):
                artifact_uri = await _upload_work_order_artifact(
                    session_id=session_id,
                    action_id=action_id,
                    execution_result=execution,
                )
                if artifact_uri:
                    logger.debug(f"Stored work-order artifact: {artifact_uri}")
                await websocket.send_json(
                    {
                        "type": "work_order",
                        "data": execution.get("work_order"),
                    }
                )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "data": f"Unknown action_id: {action_id}",
                }
            )
