"""
Work Order Management Tool
ADK tool function for creating and updating maintenance work orders.
"""

import logging
from typing import Any

from agent.tools.wrapper import tool_wrapper
from models.schemas import Priority, WorkOrder, WorkOrderStatus
from services.eam_provider import get_eam_service
from services.mutation_safety import (
    CREATE_WORK_ORDER,
    UPDATE_WORK_ORDER,
    confirmation_required_response,
    missing_required_fields,
    work_order_mutation_allowed,
    work_order_mutation_requires_confirmation,
)
from services.query_engine import QueryEngine
from services.search_service import SearchService

logger = logging.getLogger("maintenance-eye.tools.work_order")

_engine = QueryEngine()
_search_service = SearchService(_engine)


def _confirmation_required(action: str) -> bool:
    return work_order_mutation_requires_confirmation(action) and not work_order_mutation_allowed(
        action
    )


def _parse_priority(priority: str) -> Priority:
    value = (priority or "").strip().upper()
    return Priority(value)


def _parse_work_order_status(status: str) -> WorkOrderStatus:
    value = (status or "").strip().lower()
    return WorkOrderStatus(value)


@tool_wrapper
async def manage_work_order(
    action: str,
    asset_id: str = "",
    wo_id: str = "",
    description: str = "",
    problem_code: str = "",
    fault_code: str = "",
    action_code: str = "",
    failure_class: str = "",
    priority: str = "",
    assigned_to: str = "",
    notes: str = "",
    status: str = "",
) -> dict:
    """
    Create, update, retrieve, list, or search maintenance work orders.
    Mutating actions are guarded by backend confirmation policy; unconfirmed
    create/update attempts return a confirmation-required response.

    Args:
        action: One of "create", "update", "get", "list", "search".
            - "search": Find work orders by text query. Put the search terms in
              the `description` parameter. Each word is matched independently
              against wo_id, description, asset_id, and EAM codes.
              Optionally filter by priority and status.
              If no work orders are found and the asset ID appears malformed,
              returns `needs_asset_confirmation` + `guessed_assets` so the
              agent can confirm the intended asset before retrying.
        asset_id: The asset ID this work order relates to.
        wo_id: Work order ID (required for "update" and "get").
        description: Description of the issue found. For "search", put search terms here.
        problem_code: EAM problem code (e.g., "ME-003").
        fault_code: EAM fault code (e.g., "WEAR-SUR").
        action_code: Recommended action code (e.g., "REPLACE").
        failure_class: Failure classification (e.g., "MECHANICAL").
        priority: Priority level: P1 (Critical), P2 (High), P3 (Medium), P4 (Low), P5 (Planned).
        assigned_to: Technician or zone to assign to.
        notes: Additional notes to add.
        status: New status for updates (open, in_progress, completed, etc.).

    Returns:
        dict with work order details or list of work orders.
    """
    eam = get_eam_service()

    try:
        if action == "create":
            missing_fields = missing_required_fields(
                CREATE_WORK_ORDER,
                {
                    "asset_id": asset_id,
                    "description": description,
                },
            )
            if missing_fields:
                return {
                    "success": False,
                    "error": (
                        "Missing required fields for work order creation: "
                        + ", ".join(missing_fields)
                    ),
                    "missing_fields": missing_fields,
                }

            try:
                resolved_priority = _parse_priority(priority or "P3")
            except ValueError:
                allowed = ", ".join([p.value for p in Priority])
                return {
                    "success": False,
                    "error": f"Invalid priority: {priority}. Allowed: {allowed}",
                }

            if _confirmation_required(action):
                return confirmation_required_response(action)

            wo = WorkOrder(
                wo_id="",  # Will be auto-generated
                asset_id=asset_id,
                description=description,
                problem_code=problem_code,
                fault_code=fault_code,
                action_code=action_code,
                failure_class=failure_class,
                priority=resolved_priority,
                assigned_to=assigned_to,
                notes=[notes] if notes else [],
            )
            created_wo = await eam.create_work_order(wo)
            return {
                "success": True,
                "action": "created",
                "work_order": created_wo.model_dump(),
                "message": f"Work order {created_wo.wo_id} created successfully.",
            }

        elif action == "update":
            if missing_required_fields(UPDATE_WORK_ORDER, {"wo_id": wo_id}):
                return {"success": False, "error": "wo_id required for update"}
            updates: dict[str, Any] = {}
            if status:
                try:
                    updates["status"] = _parse_work_order_status(status).value
                except ValueError:
                    allowed = ", ".join([s.value for s in WorkOrderStatus])
                    return {
                        "success": False,
                        "error": f"Invalid status: {status}. Allowed: {allowed}",
                    }
            if notes:
                updates["notes"] = [notes]
            if priority:
                try:
                    updates["priority"] = _parse_priority(priority).value
                except ValueError:
                    allowed = ", ".join([p.value for p in Priority])
                    return {
                        "success": False,
                        "error": f"Invalid priority: {priority}. Allowed: {allowed}",
                    }
            if _confirmation_required(action):
                return confirmation_required_response(action)

            updated_wo = await eam.update_work_order(wo_id, updates)
            if updated_wo:
                return {
                    "success": True,
                    "action": "updated",
                    "work_order": updated_wo.model_dump(),
                }
            return {"success": False, "error": f"Work order {wo_id} not found"}

        elif action == "get":
            if not wo_id:
                return {"success": False, "error": "wo_id required for get"}
            fetched_wo = await eam.get_work_order(wo_id)
            if not fetched_wo:
                for candidate in QueryEngine.normalize_wo_id(wo_id):
                    fetched_wo = await eam.get_work_order(candidate)
                    if fetched_wo:
                        break
            if fetched_wo:
                return {"success": True, "work_order": fetched_wo.model_dump()}
            return {"success": False, "error": f"Work order {wo_id} not found"}

        elif action == "list":
            try:
                wo_status = _parse_work_order_status(status) if status else None
            except ValueError:
                allowed = ", ".join([s.value for s in WorkOrderStatus])
                return {"success": False, "error": f"Invalid status: {status}. Allowed: {allowed}"}
            work_orders = await eam.get_work_orders(asset_id=asset_id, status=wo_status)
            return {
                "success": True,
                "count": len(work_orders),
                "work_orders": [wo.model_dump() for wo in work_orders],
            }

        elif action == "search":
            search_text = description or notes or ""
            return await _search_service.search_work_orders(
                eam,
                query=search_text,
                asset_id=asset_id,
                status=status,
                priority=priority,
            )

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"Work order operation failed: {e}")
        return {"success": False, "error": str(e)}
