from __future__ import annotations

import pytest
from models.schemas import InspectionFinding, InspectionRecord, Priority, WorkOrderStatus
from services.inspection_context import (
    build_inspection_history_context,
    build_report_context,
    build_safety_protocol_context,
)

from tests.fixtures.factories import (
    FakeEAM,
    make_kb_entry,
    make_work_order,
)


def _inspection(
    inspection_id: str,
    fault_codes: list[str],
    asset_id: str = "AST-UNIT-001",
) -> InspectionRecord:
    return InspectionRecord(
        inspection_id=inspection_id,
        asset_id=asset_id,
        inspector="Field Technician",
        date="2026-04-01T12:00:00",
        findings=[
            InspectionFinding(
                finding_id=f"{inspection_id}-{index}",
                description=f"{fault_code} observed",
                severity=Priority.P3_MEDIUM,
                problem_code="ME-003",
                fault_code=fault_code,
            )
            for index, fault_code in enumerate(fault_codes, start=1)
        ],
        overall_condition="requires_attention",
    )


class EAMWithInspectionHistory(FakeEAM):
    def __init__(self, inspections: list[InspectionRecord]) -> None:
        super().__init__()
        self.inspections = inspections
        self.inspection_request: tuple[str, int] | None = None

    async def get_inspection_history(
        self, asset_id: str, limit: int = 10
    ) -> list[InspectionRecord]:
        self.inspection_request = (asset_id, limit)
        return self.inspections


@pytest.mark.unit
@pytest.mark.asyncio
async def test_history_context_collects_inspections_open_work_orders_and_recurring_issues() -> None:
    eam = EAMWithInspectionHistory(
        [
            _inspection("INSP-1", ["WEAR-SUR", "ALIGNMENT"]),
            _inspection("INSP-2", ["WEAR-SUR"]),
        ]
    )
    eam.work_orders = [
        make_work_order(wo_id="WO-OPEN", status=WorkOrderStatus.OPEN),
        make_work_order(wo_id="WO-ACTIVE", status=WorkOrderStatus.IN_PROGRESS),
        make_work_order(wo_id="WO-DONE", status=WorkOrderStatus.COMPLETED),
    ]

    result = await build_inspection_history_context(eam, "AST-UNIT-001", limit=2)

    assert eam.inspection_request == ("AST-UNIT-001", 2)
    assert result["asset_id"] == "AST-UNIT-001"
    assert result["inspection_count"] == 2
    assert [wo["wo_id"] for wo in result["open_work_orders"]] == ["WO-OPEN", "WO-ACTIVE"]
    assert result["total_work_orders"] == 3
    assert result["recurring_issues"] == [{"fault_code": "WEAR-SUR", "occurrences": 2}]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_safety_context_prefers_knowledge_base_results() -> None:
    eam = FakeEAM()
    kb_entry = make_kb_entry()
    kb_entry.title = "Safety protocol switch machines"
    eam.kb_entries = [kb_entry]

    result = await build_safety_protocol_context(eam, "switch", department="guideway")

    assert result["source"] == "knowledge_base"
    assert result["asset_type"] == "switch"
    assert result["protocols"][0]["doc_id"] == "KB-001"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_safety_context_uses_default_protocol_when_knowledge_base_has_no_match() -> None:
    eam = FakeEAM()

    result = await build_safety_protocol_context(eam, "escalator")

    assert result == {
        "source": "default",
        "asset_type": "escalator",
        "ppe_required": ["Safety boots", "High-visibility vest", "Safety glasses"],
        "loto_required": True,
        "precautions": [
            "Ensure escalator is stopped and LOTO applied before hands-on inspection",
            "Watch for pinch points at handrail entry/exit",
            "Stay clear of comb plates during any movement test",
        ],
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_context_preserves_report_shape_and_recommendation() -> None:
    eam = FakeEAM()
    eam.work_orders = [
        make_work_order(wo_id="WO-OPEN", status=WorkOrderStatus.OPEN),
        make_work_order(wo_id="WO-DONE", status=WorkOrderStatus.COMPLETED),
    ]

    result = await build_report_context(
        eam,
        asset_id="AST-UNIT-001",
        inspector_name="Max",
        findings_summary="Handrail worn",
        overall_condition="requires_immediate_action",
        report_id="RPT-UNIT",
        generated_at="2026-05-02T12:00:00",
    )

    assert result["report_id"] == "RPT-UNIT"
    assert result["generated_at"] == "2026-05-02T12:00:00"
    assert result["asset"]["asset_id"] == "AST-UNIT-001"
    assert result["inspector"] == "Max"
    assert result["overall_condition"] == "requires_immediate_action"
    assert result["findings_summary"] == "Handrail worn"
    assert [wo["wo_id"] for wo in result["open_work_orders"]] == ["WO-OPEN"]
    assert result["work_orders_created_this_session"] == []
    assert result["next_inspection_recommendation"] == (
        "Urgent \u2014 follow-up inspection within 7 days"
    )
