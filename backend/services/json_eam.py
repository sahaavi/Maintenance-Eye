"""
JSON-backed EAM Implementation
Fallback EAM service that reads from seed_data.json when Firestore is unavailable.
Supports reads from seed data and in-memory writes for work orders.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from models.schemas import (
    Asset,
    CorrectionLog,
    EAMCode,
    InspectionRecord,
    KnowledgeBaseEntry,
    WorkOrder,
    WorkOrderStatus,
)
from services.base_eam import BaseEAMService
from services.search_matcher import query_matches_text

logger = logging.getLogger("maintenance-eye.json-eam")


def _resolve_seed_path() -> Path | None:
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


class JsonEAM(BaseEAMService):
    """
    In-memory EAM service backed by seed_data.json.
    Reads are from seed data; writes (work orders, inspections) are stored in memory.
    """

    def __init__(self):
        path = _resolve_seed_path()
        if path:
            with open(path, encoding="utf-8") as f:
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

    async def get_asset(self, asset_id: str) -> Asset | None:
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
                searchable = self.build_asset_searchable(a)
                if not query_matches_text(query, searchable):
                    continue
            results.append(Asset(**a))
        return results

    # --- Work Order Operations ---

    async def get_work_order(self, wo_id: str) -> WorkOrder | None:
        data = self._work_orders.get(wo_id)
        if data:
            return WorkOrder(**data)
        return None

    async def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        self._wo_counter += 1
        work_order.wo_id = f"WO-{datetime.utcnow().strftime('%Y')}-{self._wo_counter:04d}"
        work_order.created_at = datetime.utcnow().isoformat()
        self._work_orders[work_order.wo_id] = work_order.model_dump()
        logger.info(f"Created work order (in-memory): {work_order.wo_id}")
        return work_order

    async def update_work_order(self, wo_id: str, updates: dict) -> WorkOrder | None:
        if wo_id not in self._work_orders:
            return None
        data = self._work_orders[wo_id]
        normalized_updates = self.normalize_work_order_updates(updates)
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
        status: WorkOrderStatus | None = None,
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
        status: WorkOrderStatus | None = None,
        location: str = "",
    ) -> list[WorkOrder]:
        location_asset_ids, dept_asset_ids = self.resolve_location_dept_filters(
            iter(self._assets.values()), location, department
        )

        results = []
        for wo in self._work_orders.values():
            if status and wo.get("status") != status.value:
                continue
            if priority and wo.get("priority", "").upper() != priority.upper():
                continue

            aid = wo.get("asset_id", "")
            asset = self._assets.get(aid, {})

            if location_asset_ids is not None and aid not in location_asset_ids:
                continue
            if dept_asset_ids is not None and aid not in dept_asset_ids:
                continue
            if q:
                searchable = self.build_wo_searchable(wo, asset)
                if not query_matches_text(q, searchable):
                    continue
            results.append(WorkOrder(**wo))
        return results

    async def get_locations(self) -> list[dict]:
        return self.aggregate_stations(iter(self._assets.values()))

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
        query_tokens = self.tokenize_kb_query(query) if query else []
        for k in self._knowledge_base:
            if department and k.get("department") != department:
                continue
            if asset_type and asset_type not in k.get("asset_types", []):
                continue
            if query_tokens:
                searchable = f"{k.get('title', '')} {k.get('content', '')} {' '.join(k.get('tags', []))}".lower()
                if not self.kb_tokens_match(query_tokens, searchable):
                    continue
            results.append(KnowledgeBaseEntry(**k))
        return results

    # --- Feedback Loop ---

    async def log_correction(self, correction: CorrectionLog) -> None:
        self._corrections.append(correction.model_dump())

    async def get_corrections(self, asset_id: str = "", code_type: str = "") -> list[CorrectionLog]:
        results = []
        for c in self._corrections:
            if asset_id and c.get("asset_id") != asset_id:
                continue
            if code_type and c.get("code_type") != code_type:
                continue
            results.append(CorrectionLog(**c))
        return results
