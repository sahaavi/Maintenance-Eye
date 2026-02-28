"""
Confirmation Tool
ADK tool function for the human-in-the-loop confirmation workflow.

The agent uses this tool to:
  - Propose critical actions for technician confirmation
  - Check the status of pending actions
  - Process technician responses (confirm/reject/correct)
"""

import logging
from typing import Optional

from services.confirmation_manager import (
    get_confirmation_manager,
    ActionType,
    ConfirmationStatus,
)

logger = logging.getLogger("maintenance-eye.tools.confirm")

# Session context — set by the WebSocket handler before tool invocation
_current_session_id: str = "default"


def set_session_context(session_id: str):
    """Set the active session ID for tool calls."""
    global _current_session_id
    _current_session_id = session_id


def propose_action(
    action_type: str,
    description: str,
    asset_id: str = "",
    problem_code: str = "",
    fault_code: str = "",
    action_code: str = "",
    priority: str = "P3",
    confidence: float = 0.0,
    additional_data: str = "",
) -> dict:
    """
    Propose a critical action that requires technician confirmation before
    executing. Use this whenever you want to create or modify a work order,
    escalate priority, or change a classification.

    IMPORTANT: After calling this tool, WAIT for the technician to respond
    with confirm, reject, or correct before proceeding.

    Args:
        action_type: Type of action. One of: "create_work_order",
            "update_work_order", "escalate_priority", "close_work_order",
            "change_classification".
        description: Clear description of what you're proposing, in plain
            language the technician can quickly understand.
        asset_id: The asset ID this action relates to.
        problem_code: Proposed EAM problem code (e.g., "ME-003").
        fault_code: Proposed EAM fault code (e.g., "WEAR-SUR").
        action_code: Proposed action code (e.g., "REPLACE").
        priority: Proposed priority: P1 (Critical) through P5 (Planned).
        confidence: Your confidence in this proposal (0.0 to 1.0).
        additional_data: Any other relevant details as a JSON string.

    Returns:
        dict with the action_id and a prompt for the technician.
    """
    try:
        at = ActionType(action_type)
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid action_type: {action_type}. "
                     f"Must be one of: {[e.value for e in ActionType]}"
        }

    mgr = get_confirmation_manager(_current_session_id)

    proposed_data = {}
    if asset_id:
        proposed_data["asset_id"] = asset_id
    if problem_code:
        proposed_data["problem_code"] = problem_code
    if fault_code:
        proposed_data["fault_code"] = fault_code
    if action_code:
        proposed_data["action_code"] = action_code
    if priority:
        proposed_data["priority"] = priority
    if additional_data:
        proposed_data["additional_data"] = additional_data

    action = mgr.propose_action(
        action_type=at,
        description=description,
        proposed_data=proposed_data,
        ai_confidence=confidence,
        asset_id=asset_id,
    )

    # Build a human-readable confirmation prompt
    confidence_pct = f"{confidence:.0%}" if confidence > 0 else "N/A"
    codes_str = ""
    if problem_code or fault_code or action_code:
        parts = []
        if problem_code:
            parts.append(f"Problem: {problem_code}")
        if fault_code:
            parts.append(f"Fault: {fault_code}")
        if action_code:
            parts.append(f"Action: {action_code}")
        codes_str = " | ".join(parts)

    return {
        "success": True,
        "action_id": action.action_id,
        "status": "pending",
        "confirmation_prompt": {
            "action_type": action_type,
            "description": description,
            "asset_id": asset_id,
            "priority": priority,
            "confidence": confidence_pct,
            "codes": codes_str,
            "message": (
                f"I'm proposing to {description}. "
                f"Priority: {priority}, Confidence: {confidence_pct}. "
                f"{'Codes: ' + codes_str + '. ' if codes_str else ''}"
                f"Do you confirm, reject, or want to correct anything?"
            ),
        },
        "instructions": (
            "WAIT for the technician to respond. "
            "They will confirm, reject, or provide corrections. "
            "Do NOT proceed until you receive their response."
        ),
    }


def check_pending_actions() -> dict:
    """
    Check the status of all pending actions in the current session.
    Use this if you need to remind the technician about unresolved proposals.

    Returns:
        dict with list of pending actions and session stats.
    """
    mgr = get_confirmation_manager(_current_session_id)
    pending = mgr.get_pending()
    stats = mgr.get_stats()

    return {
        "pending_count": len(pending),
        "pending_actions": [
            {
                "action_id": a.action_id,
                "action_type": a.action_type.value,
                "description": a.description,
                "asset_id": a.asset_id,
                "confidence": f"{a.ai_confidence:.0%}",
                "created_at": a.created_at,
            }
            for a in pending
        ],
        "session_stats": stats,
    }
