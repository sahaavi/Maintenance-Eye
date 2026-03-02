"""
REST API Routes
Provides endpoints for inspection history, reports, and asset lookup.
Uses get_eam_service() which returns FirestoreEAM or JsonEAM fallback transparently.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from models.schemas import WorkOrderStatus
from services.firestore_eam import get_eam_service

router = APIRouter()
logger = logging.getLogger("maintenance-eye.routes")


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Get a specific asset by ID."""
    eam = get_eam_service()
    asset = await eam.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.get("/assets")
async def search_assets(
    q: str = "",
    department: str = "",
    station: str = "",
    asset_type: str = "",
):
    """Search assets by query, department, station, or type."""
    eam = get_eam_service()
    return await eam.search_assets(
        query=q, department=department, station=station, asset_type=asset_type
    )


@router.get("/work-orders")
async def get_work_orders(
    asset_id: str = "",
    status: Optional[str] = None,
    q: str = "",
    priority: str = "",
    department: str = "",
    location: str = "",
):
    """Get work orders with optional full-text search and filters."""
    wo_status = None
    if status:
        try:
            wo_status = WorkOrderStatus(status.lower())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}") from exc

    eam = get_eam_service()
    has_advanced = q or priority or department or location
    if has_advanced:
        return await eam.search_work_orders(
            q=q, priority=priority, department=department,
            status=wo_status, location=location,
        )
    return await eam.get_work_orders(asset_id=asset_id, status=wo_status)


@router.get("/locations")
async def get_locations():
    """Get unique stations derived from assets."""
    eam = get_eam_service()
    return await eam.get_locations()


@router.get("/inspections/{asset_id}")
async def get_inspection_history(asset_id: str, limit: int = 10):
    """Get inspection history for an asset."""
    eam = get_eam_service()
    return await eam.get_inspection_history(asset_id=asset_id, limit=limit)


@router.get("/knowledge")
async def search_knowledge(q: str = "", asset_type: str = "", department: str = ""):
    """Search the maintenance knowledge base."""
    eam = get_eam_service()
    return await eam.search_knowledge_base(
        query=q or "maintenance", asset_type=asset_type, department=department
    )


@router.get("/eam-codes")
async def get_eam_codes(code_type: str = "", department: str = "", asset_type: str = ""):
    """Get EAM classification codes."""
    eam = get_eam_service()
    return await eam.get_eam_codes(
        code_type=code_type, department=department, asset_type=asset_type
    )


# ---------------------------------------------------------------------------
# Confirmation endpoints (human-in-the-loop)
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/pending")
async def get_pending_actions(session_id: str):
    """Get pending actions for a session that need technician confirmation."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    pending = mgr.get_pending()
    return {
        "session_id": session_id,
        "pending_count": len(pending),
        "actions": [a.model_dump() for a in pending],
    }


@router.post("/sessions/{session_id}/confirm/{action_id}")
async def confirm_action(session_id: str, action_id: str, notes: str = ""):
    """Technician confirms a proposed action."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    action = mgr.confirm(action_id, notes)
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return {"status": "confirmed", "action": action.model_dump()}


@router.post("/sessions/{session_id}/reject/{action_id}")
async def reject_action(session_id: str, action_id: str, notes: str = ""):
    """Technician rejects a proposed action."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    action = mgr.reject(action_id, notes)
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return {"status": "rejected", "action": action.model_dump()}


@router.post("/sessions/{session_id}/correct/{action_id}")
async def correct_action(session_id: str, action_id: str, corrections: dict = {}, notes: str = ""):
    """Technician corrects a proposed action with updated values."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    action = mgr.correct(action_id, corrections, notes)
    if not action:
        raise HTTPException(status_code=404, detail="Pending action not found")
    return {"status": "corrected", "action": action.model_dump()}


@router.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str):
    """Get confirmation workflow stats for a session."""
    from services.confirmation_manager import get_confirmation_manager
    mgr = get_confirmation_manager(session_id)
    return {"session_id": session_id, **mgr.get_stats()}


# ---------------------------------------------------------------------------
# Report generation endpoints
# ---------------------------------------------------------------------------

@router.post("/reports/generate")
async def generate_report_html(
    asset_id: str,
    inspector_name: str = "Field Technician",
    findings_summary: str = "",
    overall_condition: str = "requires_attention",
):
    """Generate an inspection report and return HTML."""
    from agent.tools.report_generator import generate_report
    from services.report_renderer import render_report_html
    from fastapi.responses import HTMLResponse

    result = await generate_report(
        asset_id=asset_id,
        inspector_name=inspector_name,
        findings_summary=findings_summary,
        overall_condition=overall_condition,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Report generation failed"))

    html = render_report_html(result["report"])
    return HTMLResponse(content=html)


@router.post("/reports/generate/pdf")
async def generate_report_pdf(
    asset_id: str,
    inspector_name: str = "Field Technician",
    findings_summary: str = "",
    overall_condition: str = "requires_attention",
):
    """Generate an inspection report and return downloadable PDF."""
    from agent.tools.report_generator import generate_report
    from services.report_renderer import render_report_pdf
    from fastapi.responses import Response

    result = await generate_report(
        asset_id=asset_id,
        inspector_name=inspector_name,
        findings_summary=findings_summary,
        overall_condition=overall_condition,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Report generation failed"))

    pdf_bytes = render_report_pdf(result["report"])
    report_id = result.get("report_id", "report")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{report_id}.pdf"',
        },
    )
