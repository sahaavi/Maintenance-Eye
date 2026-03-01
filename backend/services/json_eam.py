"""
JSON-backed EAM Implementation
Fallback EAM service that reads from seed_data.json when Firestore is unavailable.
Supports reads from seed data and in-memory writes for work orders.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.schemas import (
    Asset,
    WorkOrder,
    Priority,
    WorkOrderStatus,
    EAMCode,
    InspectionRecord,
    KnowledgeBaseEntry,
    CorrectionLog,
)
from services.eam_interface import EAMService

logger = logging.getLogger("maintenance-eye.json-eam")


def _resolve_seed_path() -> Optional[Path]:
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent / "data" / "seed_data.json",
        here.parent.parent / "data" / "seed_data.json",
        Path("/app/data/seed_data.json"),
        Path.cwd() / "data" / "seed_data.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


class JsonEAM(EAMService):
    """
    In-memory EAM service backed by seed_data.json.
    Reads are from seed data; writes (work orders, inspections) are stored in memory.
    """

    def __init__(self):
        path = _resolve_seed_path()
        if path:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            logger.info(f"JsonEAM loaded seed data from {path}")
        else:
            raw = {}
            logger.warning("JsonEAM: seed_data.json not found")

        self._assets: dict[str, dict] = {}
        for a in raw.get("assets", []):
            self._assets[a["asset_id"]] = a

        self._work_orders: dict[str, dict] = {}
        for wo in raw.get("work_orders", []):
            self._work_orders[wo["wo_id"]] = wo

        self._eam_codes: list[dict] = raw.get("eam_codes", [])
        self._inspections: list[dict] = raw.get("inspections", [])
        self._knowledge_base: list[dict] = raw.get("knowledge_base", [])
        self._corrections: list[dict] = []
        self._wo_counter = len(self._work_orders)

    # --- Asset Operations ---

    async def get_asset(self, asset_id: str) -> Optional[Asset]:
        data = self._assets.get(asset_id)
        if data:
            return Asset(**data)
        return None

    async def search_assets(
        self,
        query: str = "",
        department: str = "",
        station: str = "",
        asset_type: str = "",
    ) -> list[Asset]:
        results = []
        for a in self._assets.values():
            if department and a.get("department") != department:
                continue
            if asset_type and a.get("type") != asset_type:
                continue
            if station:
                loc = a.get("location", {})
                if station.lower() not in loc.get("station", "").lower():
                    continue
            if query:
                ql = query.lower()
                searchable = f"{a.get('name','')} {a.get('asset_id','')} {a.get('location',{}).get('station','')}".lower()
                if ql not in searchable:
                    continue
            results.append(Asset(**a))
        return results

    # --- Work Order Operations ---

    async def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        self._wo_counter += 1
        work_order.wo_id = f"WO-{datetime.utcnow().strftime('%Y')}-{self._wo_counter:04d}"
        work_order.created_at = datetime.utcnow().isoformat()
        self._work_orders[work_order.wo_id] = work_order.model_dump()
        logger.info(f"Created work order (in-memory): {work_order.wo_id}")
        return work_order

    async def update_work_order(
        self, wo_id: str, updates: dict
    ) -> Optional[WorkOrder]:
        if wo_id not in self._work_orders:
            return None
        data = self._work_orders[wo_id]
        normalized_updates = dict(updates)
        if "status" in normalized_updates:
            value = normalized_updates["status"]
            normalized_updates["status"] = (
                value.value if isinstance(value, WorkOrderStatus)
                else WorkOrderStatus(str(value).lower()).value
            )
        if "priority" in normalized_updates:
            value = normalized_updates["priority"]
            normalized_updates["priority"] = (
                value.value if isinstance(value, Priority)
                else Priority(str(value).upper()).value
            )
        for key, value in normalized_updates.items():
            if key == "notes" and isinstance(value, list):
                data.setdefault("notes", []).extend(value)
            else:
                data[key] = value
        self._work_orders[wo_id] = data
        logger.info(f"Updated work order (in-memory): {wo_id}")
        return WorkOrder(**data)

    async def get_work_orders(
        self,
        asset_id: str = "",
        status: Optional[WorkOrderStatus] = None,
    ) -> list[WorkOrder]:
        results = []
        for wo in self._work_orders.values():
            if asset_id and wo.get("asset_id") != asset_id:
                continue
            if status and wo.get("status") != status.value:
                continue
            results.append(WorkOrder(**wo))
        return results

    async def search_work_orders(
        self,
        q: str = "",
        priority: str = "",
        department: str = "",
        status: Optional[WorkOrderStatus] = None,
        location: str = "",
    ) -> list[WorkOrder]:
        # Build a set of asset_ids that match the location filter
        location_asset_ids: set[str] | None = None
        if location:
            loc_lower = location.lower()
            location_asset_ids = {
                aid for aid, a in self._assets.items()
                if loc_lower in a.get("location", {}).get("station", "").lower()
            }

        # Build a set of asset_ids that match the department filter
        dept_asset_ids: set[str] | None = None
        if department:
            dept_asset_ids = {
                aid for aid, a in self._assets.items()
                if a.get("department") == department
            }

        results = []
        for wo in self._work_orders.values():
            if status and wo.get("status") != status.value:
                continue
            if priority and wo.get("priority", "").upper() != priority.upper():
                continue
            if location_asset_ids is not None and wo.get("asset_id") not in location_asset_ids:
                continue
            if dept_asset_ids is not None and wo.get("asset_id") not in dept_asset_ids:
                continue
            if q:
                ql = q.lower()
                searchable = " ".join([
                    wo.get("wo_id", ""),
                    wo.get("description", ""),
                    wo.get("asset_id", ""),
                    wo.get("problem_code", ""),
                    wo.get("fault_code", ""),
                    wo.get("action_code", ""),
                ]).lower()
                if ql not in searchable:
                    continue
            results.append(WorkOrder(**wo))
        return results

    async def get_locations(self) -> list[dict]:
        stations: dict[str, dict] = {}
        for a in self._assets.values():
            loc = a.get("location", {})
            station = loc.get("station", "")
            if not station:
                continue
            key = station
            if key not in stations:
                stations[key] = {
                    "station": station,
                    "station_code": loc.get("station_code", ""),
                    "zone": loc.get("zone", ""),
                    "asset_count": 0,
                }
            stations[key]["asset_count"] += 1
        return sorted(stations.values(), key=lambda s: s["station"])

    # --- EAM Code Operations ---

    async def get_eam_codes(
        self,
        code_type: str = "",
        department: str = "",
        asset_type: str = "",
    ) -> list[EAMCode]:
        results = []
        for c in self._eam_codes:
            if code_type and c.get("code_type") != code_type:
                continue
            if department and c.get("department") != department:
                continue
            if asset_type and asset_type not in c.get("asset_types", []):
                continue
            results.append(EAMCode(**c))
        return results

    # --- Inspection Operations ---

    async def save_inspection(self, inspection: InspectionRecord) -> InspectionRecord:
        self._inspections.append(inspection.model_dump())
        logger.info(f"Saved inspection (in-memory): {inspection.inspection_id}")
        return inspection

    async def get_inspection_history(
        self, asset_id: str, limit: int = 10
    ) -> list[InspectionRecord]:
        results = []
        for i in self._inspections:
            if i.get("asset_id") == asset_id:
                results.append(InspectionRecord(**i))
        return sorted(results, key=lambda r: r.date, reverse=True)[:limit]

    # --- Knowledge Base ---

    async def search_knowledge_base(
        self, query: str, asset_type: str = "", department: str = ""
    ) -> list[KnowledgeBaseEntry]:
        results = []
        ql = query.lower()
        for k in self._knowledge_base:
            if department and k.get("department") != department:
                continue
            if asset_type and asset_type not in k.get("asset_types", []):
                continue
            searchable = f"{k.get('title','')} {k.get('content','')} {' '.join(k.get('tags',[]))}".lower()
            if ql in searchable:
                results.append(KnowledgeBaseEntry(**k))
        return results

    # --- Feedback Loop ---

    async def log_correction(self, correction: CorrectionLog) -> None:
        self._corrections.append(correction.model_dump())

    async def get_corrections(
        self, asset_id: str = "", code_type: str = ""
    ) -> list[CorrectionLog]:
        results = []
        for c in self._corrections:
            if asset_id and c.get("asset_id") != asset_id:
                continue
            if code_type and c.get("code_type") != code_type:
                continue
            results.append(CorrectionLog(**c))
        return results
