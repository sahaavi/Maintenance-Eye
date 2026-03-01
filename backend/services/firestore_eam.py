"""
Firestore EAM Implementation
Implements the EAM service interface using Google Cloud Firestore
with synthetic data for the hackathon.
"""

import logging
from typing import Optional
from datetime import datetime

from google.cloud import firestore

from config import settings
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

logger = logging.getLogger("maintenance-eye.firestore")


class FirestoreEAM(EAMService):
    """
    Firestore-backed EAM service for hackathon demo.
    Uses synthetic data that mirrors real Hexagon EAM structure.
    """

    def __init__(self):
        self.db = firestore.AsyncClient(
            project=settings.GCP_PROJECT_ID,
            database=settings.FIRESTORE_DATABASE,
        )
        if settings.use_emulator:
            logger.info(
                f"Using Firestore emulator at {settings.FIRESTORE_EMULATOR_HOST}"
            )
        else:
            logger.info("Using Cloud Firestore")

    # --- Asset Operations ---

    async def get_asset(self, asset_id: str) -> Optional[Asset]:
        doc = await self.db.collection("assets").document(asset_id).get()
        if doc.exists:
            return Asset(**doc.to_dict())
        return None

    async def search_assets(
        self,
        query: str = "",
        department: str = "",
        station: str = "",
        asset_type: str = "",
    ) -> list[Asset]:
        ref = self.db.collection("assets")

        if department:
            ref = ref.where(filter=firestore.FieldFilter("department", "==", department))
        if asset_type:
            ref = ref.where(filter=firestore.FieldFilter("type", "==", asset_type))

        docs = ref.stream()
        results = []
        async for doc in docs:
            asset = Asset(**doc.to_dict())
            # Client-side filtering for text search (Firestore limitation)
            if query:
                q_lower = query.lower()
                if (
                    q_lower in asset.name.lower()
                    or q_lower in asset.asset_id.lower()
                    or q_lower in asset.location.station.lower()
                    or q_lower in asset.location.station_code.lower()
                ):
                    results.append(asset)
            elif station:
                if station.lower() in asset.location.station.lower():
                    results.append(asset)
            else:
                results.append(asset)
        return results

    # --- Work Order Operations ---

    async def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        # Generate WO ID using a transaction to avoid duplicate counters
        # under concurrent create requests.
        counter_ref = self.db.collection("_counters").document("work_orders")

        @firestore.async_transactional
        async def _next_work_order_count(transaction, ref):
            counter_doc = await ref.get(transaction=transaction)
            current = counter_doc.to_dict().get("count", 0) if counter_doc.exists else 0
            next_count = int(current) + 1
            transaction.set(ref, {"count": next_count})
            return next_count

        transaction = self.db.transaction()
        count = await _next_work_order_count(transaction, counter_ref)

        work_order.wo_id = f"WO-{datetime.utcnow().strftime('%Y')}-{count:04d}"
        work_order.created_at = datetime.utcnow().isoformat()

        await (
            self.db.collection("work_orders")
            .document(work_order.wo_id)
            .set(work_order.model_dump())
        )
        logger.info(f"Created work order: {work_order.wo_id}")
        return work_order

    async def update_work_order(
        self, wo_id: str, updates: dict
    ) -> Optional[WorkOrder]:
        ref = self.db.collection("work_orders").document(wo_id)
        doc = await ref.get()
        if not doc.exists:
            return None
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
        await ref.update(normalized_updates)
        updated_doc = await ref.get()
        return WorkOrder(**updated_doc.to_dict())

    async def get_work_orders(
        self,
        asset_id: str = "",
        status: Optional[WorkOrderStatus] = None,
    ) -> list[WorkOrder]:
        ref = self.db.collection("work_orders")
        if asset_id:
            ref = ref.where(filter=firestore.FieldFilter("asset_id", "==", asset_id))
        if status:
            ref = ref.where(filter=firestore.FieldFilter("status", "==", status.value))

        docs = ref.stream()
        results = []
        async for doc in docs:
            results.append(WorkOrder(**doc.to_dict()))
        return results

    async def search_work_orders(
        self,
        q: str = "",
        priority: str = "",
        department: str = "",
        status: Optional[WorkOrderStatus] = None,
        location: str = "",
    ) -> list[WorkOrder]:
        ref = self.db.collection("work_orders")
        if status:
            ref = ref.where(filter=firestore.FieldFilter("status", "==", status.value))
        if priority:
            ref = ref.where(filter=firestore.FieldFilter("priority", "==", priority.upper()))

        # Pre-resolve location/department to asset_id sets
        location_asset_ids: set[str] | None = None
        dept_asset_ids: set[str] | None = None
        if location or department:
            asset_ref = self.db.collection("assets")
            if department:
                asset_ref = asset_ref.where(filter=firestore.FieldFilter("department", "==", department))
            asset_docs = asset_ref.stream()
            loc_lower = location.lower() if location else ""
            location_ids = set()
            dept_ids = set()
            async for doc in asset_docs:
                a = doc.to_dict()
                aid = a.get("asset_id", "")
                if department:
                    dept_ids.add(aid)
                if location and loc_lower in a.get("location", {}).get("station", "").lower():
                    location_ids.add(aid)
                elif not location:
                    location_ids.add(aid)
            if location:
                location_asset_ids = location_ids
            if department:
                dept_asset_ids = dept_ids

        docs = ref.stream()
        results = []
        async for doc in docs:
            wo = doc.to_dict()
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
        docs = self.db.collection("assets").stream()
        stations: dict[str, dict] = {}
        async for doc in docs:
            a = doc.to_dict()
            loc = a.get("location", {})
            station = loc.get("station", "")
            if not station:
                continue
            if station not in stations:
                stations[station] = {
                    "station": station,
                    "station_code": loc.get("station_code", ""),
                    "zone": loc.get("zone", ""),
                    "asset_count": 0,
                }
            stations[station]["asset_count"] += 1
        return sorted(stations.values(), key=lambda s: s["station"])

    # --- EAM Code Operations ---

    async def get_eam_codes(
        self,
        code_type: str = "",
        department: str = "",
        asset_type: str = "",
    ) -> list[EAMCode]:
        ref = self.db.collection("eam_codes")
        if code_type:
            ref = ref.where(filter=firestore.FieldFilter("code_type", "==", code_type))
        if department:
            ref = ref.where(filter=firestore.FieldFilter("department", "==", department))

        docs = ref.stream()
        results = []
        async for doc in docs:
            code = EAMCode(**doc.to_dict())
            if asset_type and asset_type not in code.asset_types:
                continue
            results.append(code)
        return results

    # --- Inspection Operations ---

    async def save_inspection(self, inspection: InspectionRecord) -> InspectionRecord:
        await (
            self.db.collection("inspections")
            .document(inspection.inspection_id)
            .set(inspection.model_dump())
        )
        logger.info(f"Saved inspection: {inspection.inspection_id}")
        return inspection

    async def get_inspection_history(
        self, asset_id: str, limit: int = 10
    ) -> list[InspectionRecord]:
        ref = (
            self.db.collection("inspections")
            .where(filter=firestore.FieldFilter("asset_id", "==", asset_id))
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        docs = ref.stream()
        results = []
        async for doc in docs:
            results.append(InspectionRecord(**doc.to_dict()))
        return results

    # --- Knowledge Base ---

    async def search_knowledge_base(
        self, query: str, asset_type: str = "", department: str = ""
    ) -> list[KnowledgeBaseEntry]:
        ref = self.db.collection("knowledge_base")
        if department:
            ref = ref.where(filter=firestore.FieldFilter("department", "==", department))

        docs = ref.stream()
        results = []
        q_lower = query.lower()
        async for doc in docs:
            entry = KnowledgeBaseEntry(**doc.to_dict())
            # Client-side text matching
            if (
                q_lower in entry.title.lower()
                or q_lower in entry.content.lower()
                or any(q_lower in tag.lower() for tag in entry.tags)
            ):
                if asset_type and asset_type not in entry.asset_types:
                    continue
                results.append(entry)
        return results

    # --- Feedback Loop ---

    async def log_correction(self, correction: CorrectionLog) -> None:
        await (
            self.db.collection("correction_log")
            .document(correction.correction_id)
            .set(correction.model_dump())
        )
        logger.info(
            f"Logged correction: {correction.original_code} → {correction.corrected_code}"
        )

    async def get_corrections(
        self, asset_id: str = "", code_type: str = ""
    ) -> list[CorrectionLog]:
        ref = self.db.collection("correction_log")
        if asset_id:
            ref = ref.where(filter=firestore.FieldFilter("asset_id", "==", asset_id))
        if code_type:
            ref = ref.where(filter=firestore.FieldFilter("code_type", "==", code_type))

        docs = ref.stream()
        results = []
        async for doc in docs:
            results.append(CorrectionLog(**doc.to_dict()))
        return results


# Singleton instance
_eam_service: Optional[EAMService] = None


def get_eam_service() -> EAMService:
    """Get or create the singleton EAM service instance.

    Tries Firestore first; falls back to in-memory JSON-backed service
    when Firestore is unavailable (no emulator, no GCP credentials).
    """
    global _eam_service
    if _eam_service is not None:
        return _eam_service

    # Try Firestore when emulator is running or in production
    if settings.FIRESTORE_EMULATOR_HOST or settings.APP_ENV == "production":
        try:
            _eam_service = FirestoreEAM()
            return _eam_service
        except Exception as e:
            logger.warning(f"Firestore init failed, falling back to JSON: {e}")

    # Fallback to JSON-backed service
    from services.json_eam import JsonEAM

    logger.info("Using JSON-backed EAM service (seed_data.json)")
    _eam_service = JsonEAM()
    return _eam_service
