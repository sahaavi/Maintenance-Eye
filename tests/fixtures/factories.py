from __future__ import annotations

from typing import Any

from models.schemas import (  # type: ignore[import-not-found]
    Asset,
    AssetLocation,
    AssetStatus,
    Department,
    EAMCode,
    EAMCodeType,
    KnowledgeBaseEntry,
    Priority,
    WorkOrder,
    WorkOrderStatus,
)


def make_asset(asset_id: str = "AST-UNIT-001", station: str = "Main Station") -> Asset:
    return Asset(
        asset_id=asset_id,
        name="Signal Cabinet",
        type="signal",
        department=Department.SIGNAL_TELECOM,
        location=AssetLocation(station=station, station_code="MS", zone="Z1"),
        equipment_code="SIG-CAB",
        manufacturer="Acme",
        model="CAB-42",
        install_date="2022-01-01",
        asset_hierarchy=["signal", "cabinet"],
        status=AssetStatus.OPERATIONAL,
    )


def make_work_order(
    wo_id: str = "WO-2026-0001",
    asset_id: str = "AST-UNIT-001",
    status: WorkOrderStatus = WorkOrderStatus.OPEN,
    priority: Priority = Priority.P3_MEDIUM,
) -> WorkOrder:
    return WorkOrder(
        wo_id=wo_id,
        asset_id=asset_id,
        status=status,
        priority=priority,
        problem_code="ME-003",
        fault_code="WEAR-SUR",
        action_code="REPAIR",
        failure_class="MECHANICAL",
        description="Surface wear on bracket",
    )


def make_eam_code(code: str = "ME-003", department: Department = Department.GUIDEWAY) -> EAMCode:
    return EAMCode(
        code_type=EAMCodeType.PROBLEM,
        code=code,
        label="Surface Wear",
        department=department,
        asset_types=["track", "switch"],
        description="Progressive wear on exposed surfaces",
        related_codes=["WEAR-SUR"],
    )


def make_kb_entry(doc_id: str = "KB-001") -> KnowledgeBaseEntry:
    return KnowledgeBaseEntry(
        doc_id=doc_id,
        title="Switch Machine Inspection",
        asset_types=["switch"],
        department=Department.GUIDEWAY,
        content="Inspect housing seals and verify alignment.",
        tags=["switch", "inspection"],
        source="maintenance-manual-v2",
    )


class FakeEAM:
    """Deterministic in-memory EAM fake for route/API tests."""

    def __init__(self) -> None:
        self.assets = [make_asset(), make_asset(asset_id="AST-UNIT-002", station="Central")]
        self.work_orders = [
            make_work_order(),
            make_work_order(
                wo_id="WO-2026-0002",
                asset_id="AST-UNIT-002",
                status=WorkOrderStatus.IN_PROGRESS,
                priority=Priority.P2_HIGH,
            ),
        ]
        self.eam_codes = [make_eam_code()]
        self.kb_entries = [make_kb_entry()]

    async def get_asset(self, asset_id: str):
        return next((a for a in self.assets if a.asset_id == asset_id), None)

    async def search_assets(
        self, query: str = "", department: str = "", station: str = "", asset_type: str = ""
    ):
        result = self.assets
        if department:
            result = [a for a in result if a.department.value == department]
        if station:
            result = [a for a in result if station.lower() in a.location.station.lower()]
        if asset_type:
            result = [a for a in result if a.type == asset_type]
        if query:
            q = query.lower()
            result = [
                a for a in result if q in f"{a.asset_id} {a.name} {a.location.station}".lower()
            ]
        return result

    async def create_work_order(self, work_order: WorkOrder):
        work_order.wo_id = f"WO-2026-{len(self.work_orders) + 1:04d}"
        self.work_orders.append(work_order)
        return work_order

    async def update_work_order(self, wo_id: str, updates: dict[str, Any]):
        for wo in self.work_orders:
            if wo.wo_id == wo_id:
                data = wo.model_dump()
                data.update(updates)
                updated = WorkOrder(**data)
                self.work_orders = [updated if x.wo_id == wo_id else x for x in self.work_orders]
                return updated
        return None

    async def get_work_orders(self, asset_id: str = "", status=None):
        result = self.work_orders
        if asset_id:
            result = [wo for wo in result if wo.asset_id == asset_id]
        if status:
            result = [wo for wo in result if wo.status == status]
        return result

    async def search_work_orders(
        self, q: str = "", priority: str = "", department: str = "", status=None, location: str = ""
    ):
        result = self.work_orders
        if status:
            result = [wo for wo in result if wo.status == status]
        if priority:
            result = [wo for wo in result if wo.priority.value == priority.upper()]
        if q:
            ql = q.lower()
            result = [
                wo for wo in result if ql in f"{wo.wo_id} {wo.description} {wo.asset_id}".lower()
            ]
        if location:
            station_by_asset = {a.asset_id: a.location.station for a in self.assets}
            result = [
                wo
                for wo in result
                if location.lower() in station_by_asset.get(wo.asset_id, "").lower()
            ]
        if department:
            dept_by_asset = {a.asset_id: a.department.value for a in self.assets}
            result = [wo for wo in result if dept_by_asset.get(wo.asset_id) == department]
        return result

    async def get_locations(self):
        out = {}
        for asset in self.assets:
            station = asset.location.station
            out.setdefault(
                station,
                {
                    "station": station,
                    "station_code": asset.location.station_code,
                    "zone": asset.location.zone,
                    "asset_count": 0,
                },
            )
            out[station]["asset_count"] += 1
        return sorted(out.values(), key=lambda s: s["station"])

    async def get_inspection_history(self, asset_id: str, limit: int = 10):
        return []

    async def search_knowledge_base(self, query: str, asset_type: str = "", department: str = ""):
        result = self.kb_entries
        if asset_type:
            result = [k for k in result if asset_type in k.asset_types]
        if department:
            result = [k for k in result if k.department.value == department]
        if query:
            ql = query.lower()
            result = [k for k in result if ql in f"{k.title} {k.content}".lower()]
        return result

    async def get_eam_codes(self, code_type: str = "", department: str = "", asset_type: str = ""):
        result = self.eam_codes
        if code_type:
            result = [c for c in result if c.code_type.value == code_type]
        if department:
            result = [c for c in result if c.department.value == department]
        if asset_type:
            result = [c for c in result if asset_type in c.asset_types]
        return result

    async def save_inspection(self, inspection):
        return inspection

    async def log_correction(self, correction):
        return None

    async def get_corrections(self, asset_id: str = "", code_type: str = ""):
        return []
