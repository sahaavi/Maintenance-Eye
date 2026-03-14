"""
Work Order Management Tool
ADK tool function for creating and updating maintenance work orders.
"""

import logging

from models.schemas import Priority, WorkOrder, WorkOrderStatus
from services.firestore_eam import get_eam_service
from services.query_engine import QueryEngine

logger = logging.getLogger("maintenance-eye.tools.work_order")

_engine = QueryEngine()


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
            missing_fields: list[str] = []
            if not (asset_id or "").strip():
                missing_fields.append("asset_id")
            if not (description or "").strip():
                missing_fields.append("description")
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
            # Try direct lookup first, then normalized ID candidates
            wo = await eam.get_work_order(wo_id)
            if not wo:
                for candidate in QueryEngine.normalize_wo_id(wo_id):
                    wo = await eam.get_work_order(candidate)
                    if wo:
                        break
            if wo:
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
            # Use query engine to normalize and expand search terms
            search_text = description or notes or ""
            parsed = _engine.build_query(search_text)

            # Resolve status from explicit param or extracted filter
            try:
                wo_status = _parse_work_order_status(status) if status else None
            except ValueError:
                wo_status = None
            if not wo_status and "status" in parsed.filters:
                try:
                    wo_status = _parse_work_order_status(parsed.filters["status"])
                except ValueError:
                    pass

            # Resolve priority from explicit param or extracted filter
            resolved_priority = priority or parsed.filters.get("priority", "")

            # Resolve department from extracted filter
            resolved_department = parsed.filters.get("department", "")

            # Use normalized terms + extracted asset IDs for search
            # Asset IDs get stripped from normalized_terms during cleaning,
            # but they match against asset_id in the searchable text
            search_parts = list(parsed.normalized_terms)
            existing_upper = {part.upper() for part in search_parts}
            for eid in parsed.extracted_ids:
                upper = eid.upper()
                if not upper.startswith("WO-") and upper not in existing_upper:
                    search_parts.append(upper)
                    existing_upper.add(upper)
            # Also include explicit asset_id param if provided
            if asset_id and asset_id.upper() not in existing_upper:
                search_parts.append(asset_id.upper())
            q_text = " ".join(search_parts)

            result = await eam.search_work_orders(
                q=q_text,
                priority=resolved_priority,
                department=resolved_department,
                status=wo_status,
                location=parsed.filters.get("location", ""),
            )

            # If few results, try with expanded terms as fallback
            # IMPORTANT: preserve all filters from the original query
            if len(result) < 3 and parsed.expanded_terms:
                expanded_q = " ".join(parsed.expanded_terms)
                expanded_result = await eam.search_work_orders(
                    q=expanded_q,
                    priority=resolved_priority,
                    department=resolved_department,
                    status=wo_status,
                    location=parsed.filters.get("location", ""),
                )
                existing_ids = {wo.wo_id for wo in result}
                for wo in expanded_result:
                    if wo.wo_id not in existing_ids:
                        result.append(wo)

            response = {
                "success": True,
                "count": len(result),
                "work_orders": [wo.model_dump() for wo in result[:20]],
            }
            if not result:
                hints = QueryEngine.extract_asset_hints(search_text)
                suggestions = await _engine.suggest_asset_candidates(search_text, eam, limit=3)
                if suggestions:
                    suggestion_ids = ", ".join(s["asset_id"] for s in suggestions)
                    hinted = ", ".join(hints) if hints else "that asset ID"
                    response.update(
                        {
                            "needs_asset_confirmation": True,
                            "attempted_asset_hints": hints,
                            "guessed_assets": suggestions,
                            "message": (
                                f"No work orders found for {hinted}. Did you mean {suggestion_ids}?"
                            ),
                        }
                    )
                elif hints:
                    hinted = ", ".join(hints)
                    response.update(
                        {
                            "no_asset_match": True,
                            "attempted_asset_hints": hints,
                            "message": (
                                f"No asset found matching {hinted}. "
                                "Please confirm the exact asset tag."
                            ),
                        }
                    )
            return response

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        logger.error(f"Work order operation failed: {e}")
        return {"success": False, "error": str(e)}
