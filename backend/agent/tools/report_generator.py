"""
Report Generator Tool
ADK tool function for generating inspection reports.
"""

import logging
from datetime import datetime

from agent.tools.wrapper import tool_wrapper
from services.eam_provider import get_eam_service
from services.inspection_context import build_report_context
from services.storage_service import get_storage_service

logger = logging.getLogger("maintenance-eye.tools.report")


@tool_wrapper
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
        report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        report_date = datetime.utcnow().isoformat()

        report = await build_report_context(
            eam,
            asset_id=asset_id,
            inspector_name=inspector_name,
            findings_summary=findings_summary,
            overall_condition=overall_condition,
            report_id=report_id,
            generated_at=report_date,
        )

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
