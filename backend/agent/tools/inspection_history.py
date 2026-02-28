"""
Inspection History Tool
ADK tool function for retrieving past inspection records.
"""

import asyncio
import logging

from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.history")


def get_inspection_history(
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

    try:
        inspections = asyncio.get_event_loop().run_until_complete(
            eam.get_inspection_history(asset_id, limit=limit)
        )
        work_orders = asyncio.get_event_loop().run_until_complete(
            eam.get_work_orders(asset_id=asset_id)
        )

        # Identify recurring issues
        fault_counts: dict[str, int] = {}
        for insp in inspections:
            for finding in insp.findings:
                key = finding.fault_code
                fault_counts[key] = fault_counts.get(key, 0) + 1

        recurring = [
            {"fault_code": code, "occurrences": count}
            for code, count in fault_counts.items()
            if count > 1
        ]

        open_wos = [wo for wo in work_orders if wo.status in ("open", "in_progress")]

        return {
            "asset_id": asset_id,
            "inspection_count": len(inspections),
            "inspections": [i.model_dump() for i in inspections],
            "open_work_orders": [wo.model_dump() for wo in open_wos],
            "recurring_issues": recurring,
            "total_work_orders": len(work_orders),
        }

    except Exception as e:
        logger.error(f"History lookup failed: {e}")
        return {"asset_id": asset_id, "error": str(e), "inspections": []}
