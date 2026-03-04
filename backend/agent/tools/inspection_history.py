"""
Inspection History Tool
ADK tool function for retrieving past inspection records.
"""

import logging

from models.schemas import WorkOrderStatus
from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.history")

OPEN_WORK_ORDER_STATUSES = {WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value}


def _status_value(status: object) -> str:
    return status.value if isinstance(status, WorkOrderStatus) else str(status)


from agent.tools.wrapper import tool_wrapper

@tool_wrapper
async def get_inspection_history(
    asset_id: str,
    limit: int = 5,
) -> dict:
    """
    Retrieve past inspection records and related work orders for an asset.
    Use this to check for recurring issues, past failures, and maintenance patterns.

    Args:
        asset_id: The asset ID to get history for (e.g., "ESC-SC-003").
        limit: Maximum number of past inspections to return (default 5).

    Returns:
        dict with inspection history, related work orders, and failure patterns.
    """
    eam = get_eam_service()

    results = {
        "asset_id": asset_id,
        "inspection_count": 0,
        "inspections": [],
        "open_work_orders": [],
        "recurring_issues": [],
        "total_work_orders": 0,
    }

    # 1. Fetch Inspections
    try:
        inspections = await eam.get_inspection_history(asset_id, limit=limit)
        results["inspections"] = [i.model_dump() for i in inspections]
        results["inspection_count"] = len(inspections)
        
        # Identify recurring issues from inspections
        fault_counts: dict[str, int] = {}
        for insp in inspections:
            for finding in insp.findings:
                key = finding.fault_code
                fault_counts[key] = fault_counts.get(key, 0) + 1

        results["recurring_issues"] = [
            {"fault_code": code, "occurrences": count}
            for code, count in fault_counts.items()
            if count > 1
        ]
    except Exception as e:
        logger.error(f"History lookup (inspections) failed for {asset_id}: {e}")
        results["inspection_error"] = str(e)

    # 2. Fetch Work Orders
    try:
        work_orders = await eam.get_work_orders(asset_id=asset_id)
        results["total_work_orders"] = len(work_orders)
        
        open_wos = [
            wo for wo in work_orders if _status_value(wo.status) in OPEN_WORK_ORDER_STATUSES
        ]
        results["open_work_orders"] = [wo.model_dump() for wo in open_wos]
    except Exception as e:
        logger.error(f"History lookup (work orders) failed for {asset_id}: {e}")
        results["work_order_error"] = str(e)

    return results
