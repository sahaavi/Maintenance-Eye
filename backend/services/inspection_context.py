"""
Shared inspection context helpers for agent tools and report generation.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from models.schemas import WorkOrderStatus

logger = logging.getLogger("maintenance-eye.inspection-context")

OPEN_WORK_ORDER_STATUSES = {WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value}

DEFAULT_SAFETY = {
    "escalator": {
        "ppe": ["Safety boots", "High-visibility vest", "Safety glasses"],
        "loto_required": True,
        "precautions": [
            "Ensure escalator is stopped and LOTO applied before hands-on inspection",
            "Watch for pinch points at handrail entry/exit",
            "Stay clear of comb plates during any movement test",
        ],
    },
    "elevator": {
        "ppe": ["Safety boots", "High-visibility vest", "Hard hat"],
        "loto_required": True,
        "precautions": [
            "Ensure car is secured with LOTO before pit or top-of-car entry",
            "Verify emergency stop is engaged",
            "Follow confined space procedures for pit entry",
        ],
    },
    "switch_machine": {
        "ppe": ["Safety boots", "High-visibility vest", "Hard hat", "Safety glasses"],
        "loto_required": True,
        "precautions": [
            "Coordinate with control center before any switch inspection",
            "Stay clear of moving parts \u2014 switch machines actuate with high force",
            "Track-level work requires flagging protection",
        ],
    },
    "default": {
        "ppe": ["Safety boots", "High-visibility vest", "Safety glasses"],
        "loto_required": False,
        "precautions": [
            "Ensure area is safe before starting inspection",
            "Be aware of your surroundings and potential hazards",
            "Follow site-specific safety procedures",
        ],
    },
}


def status_value(status: object) -> str:
    return status.value if isinstance(status, WorkOrderStatus) else str(status)


def is_open_work_order_status(status: object) -> bool:
    return status_value(status) in OPEN_WORK_ORDER_STATUSES


def dump_model(model: Any) -> dict[str, Any]:
    return cast(dict[str, Any], model.model_dump(mode="json"))


def open_work_orders(work_orders: list[Any]) -> list[Any]:
    return [wo for wo in work_orders if is_open_work_order_status(wo.status)]


def recurring_issues_from_inspections(inspections: list[Any]) -> list[dict[str, Any]]:
    fault_counts: dict[str, int] = {}
    for inspection in inspections:
        for finding in inspection.findings:
            key = finding.fault_code
            fault_counts[key] = fault_counts.get(key, 0) + 1

    return [
        {"fault_code": code, "occurrences": count}
        for code, count in fault_counts.items()
        if count > 1
    ]


async def build_inspection_history_context(eam: Any, asset_id: str, limit: int = 5) -> dict:
    results: dict[str, Any] = {
        "asset_id": asset_id,
        "inspection_count": 0,
        "inspections": [],
        "open_work_orders": [],
        "recurring_issues": [],
        "total_work_orders": 0,
    }

    try:
        inspections = await eam.get_inspection_history(asset_id, limit=limit)
        results["inspections"] = [dump_model(inspection) for inspection in inspections]
        results["inspection_count"] = len(inspections)
        results["recurring_issues"] = recurring_issues_from_inspections(inspections)
    except Exception as exc:
        logger.error(f"History lookup (inspections) failed for {asset_id}: {exc}")
        results["inspection_error"] = str(exc)

    try:
        work_orders = await eam.get_work_orders(asset_id=asset_id)
        results["total_work_orders"] = len(work_orders)
        results["open_work_orders"] = [
            dump_model(work_order) for work_order in open_work_orders(work_orders)
        ]
    except Exception as exc:
        logger.error(f"History lookup (work orders) failed for {asset_id}: {exc}")
        results["work_order_error"] = str(exc)

    return results


async def build_safety_protocol_context(
    eam: Any,
    asset_type: str,
    department: str = "",
) -> dict:
    try:
        results = await eam.search_knowledge_base(
            query=f"safety protocol {asset_type}",
            asset_type=asset_type,
            department=department,
        )

        if results:
            return {
                "source": "knowledge_base",
                "asset_type": asset_type,
                "protocols": [dump_model(result) for result in results[:3]],
            }

        protocol = DEFAULT_SAFETY.get(asset_type, DEFAULT_SAFETY["default"])
        return {
            "source": "default",
            "asset_type": asset_type,
            "ppe_required": protocol["ppe"],
            "loto_required": protocol["loto_required"],
            "precautions": protocol["precautions"],
        }

    except Exception as exc:
        logger.error(f"Safety protocol lookup failed: {exc}")
        protocol = DEFAULT_SAFETY["default"]
        return {
            "source": "fallback",
            "asset_type": asset_type,
            "ppe_required": protocol["ppe"],
            "loto_required": protocol["loto_required"],
            "precautions": protocol["precautions"],
            "error": str(exc),
        }


async def build_report_context(
    eam: Any,
    asset_id: str,
    inspector_name: str,
    findings_summary: str,
    overall_condition: str,
    report_id: str,
    generated_at: str,
) -> dict:
    asset = await eam.get_asset(asset_id)
    work_orders = await eam.get_work_orders(asset_id=asset_id)

    return {
        "report_id": report_id,
        "generated_at": generated_at,
        "asset": dump_model(asset) if asset else {"asset_id": asset_id},
        "inspector": inspector_name,
        "overall_condition": overall_condition,
        "findings_summary": findings_summary,
        "open_work_orders": [
            dump_model(work_order) for work_order in open_work_orders(work_orders)
        ],
        "work_orders_created_this_session": [],
        "next_inspection_recommendation": recommend_next_inspection(overall_condition),
    }


def recommend_next_inspection(condition: str) -> str:
    recommendations = {
        "good": "Standard schedule \u2014 next inspection in 90 days",
        "requires_attention": "Shortened interval \u2014 next inspection in 30 days",
        "requires_immediate_action": "Urgent \u2014 follow-up inspection within 7 days",
        "out_of_service": (
            "Asset removed from service \u2014 inspect before returning to operation"
        ),
    }
    return recommendations.get(condition, "Follow standard inspection schedule")
