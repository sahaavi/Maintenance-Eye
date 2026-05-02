"""
First-class confirmation workflow service.

This module owns the domain transition from a resolved human confirmation to
deterministic backend execution. API and WebSocket handlers should only adapt
transport message shapes around this interface.
"""

import ast
import json
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from services.confirmation_manager import ActionType, ConfirmationManager, PendingAction
from services.mutation_safety import confirmed_mutation, missing_required_fields
from services.storage_service import get_storage_service


@dataclass(frozen=True)
class ConfirmationWorkflowResult:
    """Resolved confirmation action plus optional execution result."""

    action: PendingAction
    execution: dict | None = None

    @property
    def status(self) -> str:
        return str(self.action.status.value)


def decode_additional_data(value: object) -> dict:
    """Best-effort parse of additional_data payload from tool input."""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    try:
        parsed = ast.literal_eval(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def build_action_payload(action: PendingAction) -> dict:
    """Merge confirmation proposed_data and additional_data into a single dict."""
    payload = dict(action.proposed_data or {})
    extra = decode_additional_data(payload.pop("additional_data", ""))
    if extra:
        payload.update(extra)
    return payload


async def upload_work_order_artifact(
    session_id: str,
    action_id: str,
    execution_result: dict,
) -> str | None:
    """Persist confirmed work-order payload to GCS for audit traceability."""
    storage = get_storage_service()
    if not storage.enabled:
        return None
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
    object_path = f"sessions/{session_id}/work_orders/{timestamp}-{action_id}.json"
    return cast(str | None, await storage.upload_json(execution_result, object_path))


async def manage_confirmed_work_order(**kwargs: object) -> dict:
    from agent.tools.work_order import manage_work_order

    return cast(dict, await manage_work_order(**kwargs))


class ConfirmationWorkflow:
    """Confirm, reject, correct, and execute pending technician actions."""

    def __init__(self, manager: ConfirmationManager):
        self.manager = manager

    async def confirm(
        self, action_id: str, technician_notes: str = ""
    ) -> ConfirmationWorkflowResult | None:
        action = self.manager.confirm(action_id, technician_notes)
        if not action:
            return None
        return ConfirmationWorkflowResult(action=action, execution=await self.execute(action))

    async def reject(
        self, action_id: str, technician_notes: str = ""
    ) -> ConfirmationWorkflowResult | None:
        action = self.manager.reject(action_id, technician_notes)
        if not action:
            return None
        return ConfirmationWorkflowResult(action=action)

    async def correct(
        self,
        action_id: str,
        corrections: dict,
        technician_notes: str = "",
    ) -> ConfirmationWorkflowResult | None:
        action = self.manager.correct(action_id, corrections, technician_notes)
        if not action:
            return None
        return ConfirmationWorkflowResult(action=action, execution=await self.execute(action))

    async def execute(self, action: PendingAction) -> dict:
        """
        Execute a confirmed/corrected action deterministically.
        This avoids relying on the model to re-issue tool calls after confirmation.
        """
        payload = build_action_payload(action)
        action_type = action.action_type

        if action_type == ActionType.CREATE_WORK_ORDER:
            effective_asset_id = payload.get("asset_id", action.asset_id)
            effective_description = payload.get("description", action.description)
            missing_fields = missing_required_fields(
                action_type.value,
                {
                    "asset_id": effective_asset_id,
                    "description": effective_description,
                },
            )
            if missing_fields:
                return {
                    "success": False,
                    "error": (
                        "Cannot execute confirmed create_work_order; missing required fields: "
                        + ", ".join(missing_fields)
                    ),
                    "missing_fields": missing_fields,
                }

            with confirmed_mutation(action_type.value):
                return await manage_confirmed_work_order(
                    action="create",
                    asset_id=effective_asset_id,
                    description=effective_description,
                    problem_code=payload.get("problem_code", ""),
                    fault_code=payload.get("fault_code", ""),
                    action_code=payload.get("action_code", ""),
                    failure_class=payload.get("failure_class", "UNSPECIFIED"),
                    priority=payload.get("priority", "P3"),
                    assigned_to=payload.get("assigned_to", ""),
                    notes=payload.get("notes", action.technician_notes or ""),
                )

        if action_type == ActionType.UPDATE_WORK_ORDER:
            with confirmed_mutation(action_type.value):
                return await manage_confirmed_work_order(
                    action="update",
                    wo_id=payload.get("wo_id", ""),
                    status=payload.get("status", ""),
                    priority=payload.get("priority", ""),
                    notes=payload.get("notes", action.technician_notes or ""),
                )

        if action_type == ActionType.CLOSE_WORK_ORDER:
            with confirmed_mutation(action_type.value):
                return await manage_confirmed_work_order(
                    action="update",
                    wo_id=payload.get("wo_id", ""),
                    status="completed",
                    notes=payload.get(
                        "notes", action.technician_notes or "Closed by technician confirmation"
                    ),
                )

        if action_type == ActionType.ESCALATE_PRIORITY:
            with confirmed_mutation(action_type.value):
                return await manage_confirmed_work_order(
                    action="update",
                    wo_id=payload.get("wo_id", ""),
                    priority=payload.get("priority", ""),
                    notes=payload.get(
                        "notes",
                        action.technician_notes or "Priority escalated by technician confirmation",
                    ),
                )

        return {
            "success": False,
            "error": f"Action type {action_type.value} is not executable via backend automation.",
        }
