"""
Report Generator Tool
ADK tool function for generating inspection reports.
"""

import logging
from datetime import datetime

from models.schemas import WorkOrderStatus
from services.firestore_eam import get_eam_service
from services.storage_service import get_storage_service

logger = logging.getLogger("maintenance-eye.tools.report")

OPEN_WORK_ORDER_STATUSES = {WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value}


def _status_value(status: object) -> str:
    return status.value if isinstance(status, WorkOrderStatus) else str(status)


async def generate_report(
    asset_id: str,
    inspector_name: str = "Field Technician",
    findings_summary: str = "",
    overall_condition: str = "requires_attention",
) -> dict:
    """
    Generate a structured inspection report for the current session.
    Call this when the technician says they are done inspecting or
    asks for a report.

    Args:
        asset_id: The asset that was inspected.
        inspector_name: Name of the technician performing the inspection.
        findings_summary: Summary of all findings from this inspection session.
        overall_condition: Overall condition assessment: "good", "requires_attention",
            "requires_immediate_action", or "out_of_service".

    Returns:
        dict with the generated report details and a reference ID.
    """
    eam = get_eam_service()

    try:
        # Get asset info
        asset = await eam.get_asset(asset_id)

        # Get recent work orders
        work_orders = await eam.get_work_orders(asset_id=asset_id)
        open_wos = [
            wo for wo in work_orders if _status_value(wo.status) in OPEN_WORK_ORDER_STATUSES
        ]

        report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        report_date = datetime.utcnow().isoformat()

        report = {
            "report_id": report_id,
            "generated_at": report_date,
            "asset": asset.model_dump() if asset else {"asset_id": asset_id},
            "inspector": inspector_name,
            "overall_condition": overall_condition,
            "findings_summary": findings_summary,
            "open_work_orders": [wo.model_dump() for wo in open_wos],
            "work_orders_created_this_session": [],
            "next_inspection_recommendation": _recommend_next_inspection(overall_condition),
        }

        logger.info(f"Generated report: {report_id}")

        report_storage_uri = None
        storage = get_storage_service()
        if storage.enabled:
            object_path = storage.build_report_object_path(report_id)
            report_storage_uri = await storage.upload_json(report, object_path)

        return {
            "success": True,
            "report_id": report_id,
            "report": report,
            "report_storage_uri": report_storage_uri,
            "message": f"Inspection report {report_id} generated successfully.",
        }

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return {"success": False, "error": str(e)}


def _recommend_next_inspection(condition: str) -> str:
    """Recommend next inspection date based on condition."""
    recommendations = {
        "good": "Standard schedule — next inspection in 90 days",
        "requires_attention": "Shortened interval — next inspection in 30 days",
        "requires_immediate_action": "Urgent — follow-up inspection within 7 days",
        "out_of_service": "Asset removed from service — inspect before returning to operation",
    }
    return recommendations.get(condition, "Follow standard inspection schedule")
