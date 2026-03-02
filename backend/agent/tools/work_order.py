"""
Work Order Management Tool
ADK tool function for creating and updating maintenance work orders.
"""

import logging

from models.schemas import WorkOrder, Priority, WorkOrderStatus
from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.work_order")


def _parse_priority(priority: str) -> Priority:
    value = (priority or "").strip().upper()
    return Priority(value)


def _parse_work_order_status(status: str) -> WorkOrderStatus:
    value = (status or "").strip().lower()
    return WorkOrderStatus(value)


from agent.tools.wrapper import tool_wrapper

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
    Create or update a maintenance work order. ALWAYS ask the technician
    for confirmation before creating a work order.

    Args:
        action: One of "create", "update", "get", "list", "search".
            - "search": Find work orders by text query. Put the search terms in
              the `description` parameter. Each word is matched independently
              against wo_id, description, asset_id, and EAM codes.
              Optionally filter by priority and status.
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
            try:
                resolved_priority = _parse_priority(priority or "P3")
            except ValueError:
                allowed = ", ".join([p.value for p in Priority])
                return {"success": False, "error": f"Invalid priority: {priority}. Allowed: {allowed}"}

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
            result = await eam.create_work_order(wo)
            return {
                "success": True,
                "action": "created",
                "work_order": result.model_dump(),
                "message": f"Work order {result.wo_id} created successfully.",
            }

        elif action == "update":
            if not wo_id:
                return {"success": False, "error": "wo_id required for update"}
            updates = {}
            if status:
                try:
                    updates["status"] = _parse_work_order_status(status).value
                except ValueError:
                    allowed = ", ".join([s.value for s in WorkOrderStatus])
                    return {"success": False, "error": f"Invalid status: {status}. Allowed: {allowed}"}
            if notes:
                updates["notes"] = [notes]
            if priority:
                try:
                    updates["priority"] = _parse_priority(priority).value
                except ValueError:
                    allowed = ", ".join([p.value for p in Priority])
                    return {"success": False, "error": f"Invalid priority: {priority}. Allowed: {allowed}"}
            result = await eam.update_work_order(wo_id, updates)
            if result:
                return {
                    "success": True,
                    "action": "updated",
                    "work_order": result.model_dump(),
                }
            return {"success": False, "error": f"Work order {wo_id} not found"}

        elif action == "get":
            if not wo_id:
                return {"success": False, "error": "wo_id required for get"}
            result = await eam.get_work_orders(asset_id=asset_id)
            for wo in result:
                if wo.wo_id == wo_id:
                    return {"success": True, "work_order": wo.model_dump()}
            return {"success": False, "error": f"Work order {wo_id} not found"}

        elif action == "list":
            try:
                wo_status = _parse_work_order_status(status) if status else None
            except ValueError:
                allowed = ", ".join([s.value for s in WorkOrderStatus])
                return {"success": False, "error": f"Invalid status: {status}. Allowed: {allowed}"}
            result = await eam.get_work_orders(asset_id=asset_id, status=wo_status)
            return {
                "success": True,
                "count": len(result),
                "work_orders": [wo.model_dump() for wo in result],
            }

        elif action == "search":
            # Search work orders by text query across description, asset_id, codes
            try:
                wo_status = _parse_work_order_status(status) if status else None
            except ValueError:
                wo_status = None
            result = await eam.search_work_orders(
                q=description or notes or "",
                priority=priority,
                department="",
                status=wo_status,
            )
            return {
                "success": True,
                "count": len(result),
                "work_orders": [wo.model_dump() for wo in result[:20]],
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"Work order operation failed: {e}")
        return {"success": False, "error": str(e)}
