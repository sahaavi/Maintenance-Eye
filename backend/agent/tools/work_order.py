"""
Work Order Management Tool
ADK tool function for creating and updating maintenance work orders.
"""

import asyncio
import logging
from typing import Optional

from models.schemas import WorkOrder, Priority, WorkOrderStatus
from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.work_order")


def manage_work_order(
    action: str,
    asset_id: str = "",
    wo_id: str = "",
    description: str = "",
    problem_code: str = "",
    fault_code: str = "",
    action_code: str = "",
    failure_class: str = "",
    priority: str = "P3",
    assigned_to: str = "",
    notes: str = "",
    status: str = "",
) -> dict:
    """
    Create or update a maintenance work order. ALWAYS ask the technician
    for confirmation before creating a work order.

    Args:
        action: One of "create", "update", "get", "list".
        asset_id: The asset ID this work order relates to.
        wo_id: Work order ID (required for "update" and "get").
        description: Description of the issue found.
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
            wo = WorkOrder(
                wo_id="",  # Will be auto-generated
                asset_id=asset_id,
                description=description,
                problem_code=problem_code,
                fault_code=fault_code,
                action_code=action_code,
                failure_class=failure_class,
                priority=Priority(priority),
                assigned_to=assigned_to,
                notes=[notes] if notes else [],
            )
            result = asyncio.get_event_loop().run_until_complete(
                eam.create_work_order(wo)
            )
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
                updates["status"] = status
            if notes:
                updates["notes"] = firestore.ArrayUnion([notes])
            if priority:
                updates["priority"] = priority
            result = asyncio.get_event_loop().run_until_complete(
                eam.update_work_order(wo_id, updates)
            )
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
            result = asyncio.get_event_loop().run_until_complete(
                eam.get_work_orders(asset_id=asset_id)
            )
            for wo in result:
                if wo.wo_id == wo_id:
                    return {"success": True, "work_order": wo.model_dump()}
            return {"success": False, "error": f"Work order {wo_id} not found"}

        elif action == "list":
            wo_status = WorkOrderStatus(status) if status else None
            result = asyncio.get_event_loop().run_until_complete(
                eam.get_work_orders(asset_id=asset_id, status=wo_status)
            )
            return {
                "success": True,
                "count": len(result),
                "work_orders": [wo.model_dump() for wo in result],
            }

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"Work order operation failed: {e}")
        return {"success": False, "error": str(e)}
