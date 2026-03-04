"""
Firestore EAM Implementation
Implements the EAM service interface using Google Cloud Firestore
with synthetic data for the hackathon.
"""

import logging
import re
from typing import Optional
from datetime import datetime

from google.cloud import firestore
import google.auth
from google.auth.exceptions import DefaultCredentialsError

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
            data = doc.to_dict()
            asset = Asset(**data)
            # Client-side filtering for text search (Firestore limitation)
            if query:
                searchable = " ".join([
                    asset.name,
                    asset.asset_id,
                    asset.type,
                    asset.department,
                    data.get("equipment_code", ""),
                    data.get("manufacturer", ""),
                    data.get("model", ""),
                    asset.location.station,
                    asset.location.station_code,
                    getattr(asset.location, "zone", ""),
                    " ".join(data.get("asset_hierarchy", [])),
                ]).lower()
                # Tokenized matching: all query words must appear
                query_tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
                if all(token in searchable for token in query_tokens):
                    results.append(asset)
            elif station:
                if station.lower() in asset.location.station.lower():
                    results.append(asset)
            else:
                results.append(asset)
        return results

    # --- Work Order Operations ---

    async def get_work_order(self, wo_id: str) -> Optional[WorkOrder]:
        doc = await self.db.collection("work_orders").document(wo_id).get()
        if doc.exists:
            return WorkOrder(**doc.to_dict())
        return None

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

        # Fetch all assets for joining/enriching the search results
        # In a real system we would use more efficient joins/indices, but
        # for synthetic data and small collections, this is robust.
        asset_map = {}
        asset_docs = self.db.collection("assets").stream()
        async for doc in asset_docs:
            a = doc.to_dict()
            asset_map[a.get("asset_id", "")] = a

        docs = ref.stream()
        results = []
        async for doc in docs:
            wo = doc.to_dict()
            aid = wo.get("asset_id", "")
            asset = asset_map.get(aid, {})

            if location_asset_ids is not None and aid not in location_asset_ids:
                continue
            if dept_asset_ids is not None and aid not in dept_asset_ids:
                continue

            if q:
                searchable = " ".join([
                    wo.get("wo_id", ""),
                    wo.get("description", ""),
                    aid,
                    asset.get("name", ""),
                    asset.get("location", {}).get("station", ""),
                    wo.get("problem_code", ""),
                    wo.get("fault_code", ""),
                    wo.get("action_code", ""),
                    wo.get("assigned_to", ""),
                ]).lower()
                # Tokenized matching: all query words must appear
                query_tokens = re.findall(r"[a-zA-Z0-9]+", q.lower())
                if not all(token in searchable for token in query_tokens):
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
        try:
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
        except Exception as e:
            # Fallback for missing indices in production Cloud Firestore
            if "index" in str(e).lower() or "precondition" in str(e).lower() or "400" in str(e):
                logger.warning(f"Inspection history index missing for {asset_id}, falling back to unordered search: {e}")
                ref = (
                    self.db.collection("inspections")
                    .where(filter=firestore.FieldFilter("asset_id", "==", asset_id))
                    .limit(limit)
                )
                docs = ref.stream()
                results = []
                async for doc in docs:
                    results.append(InspectionRecord(**doc.to_dict()))
                return sorted(results, key=lambda r: r.date, reverse=True)
            raise e

    # --- Knowledge Base ---

    # Words that describe document type, not content — strip from KB queries
    _KB_META_WORDS = frozenset({
        "protocol", "procedure", "manual", "guide", "guidelines", "standard",
        "standards", "document", "checklist", "instructions", "handbook",
        "specification", "reference", "sop",
    })

    async def search_knowledge_base(
        self, query: str, asset_type: str = "", department: str = ""
    ) -> list[KnowledgeBaseEntry]:
        ref = self.db.collection("knowledge_base")
        if department:
            ref = ref.where(filter=firestore.FieldFilter("department", "==", department))

        docs = ref.stream()
        results = []
        # Robust tokenization
        query_tokens = [
            t for t in re.findall(r"[a-zA-Z0-9]+", query.lower())
            if t not in self._KB_META_WORDS
        ] if query else []
        
        async for doc in docs:
            entry = KnowledgeBaseEntry(**doc.to_dict())
            if asset_type and asset_type not in entry.asset_types:
                continue
            if query_tokens:
                searchable = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
                if not all(token in searchable for token in query_tokens):
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


def _has_firestore_runtime() -> bool:
    """
    Detect whether Firestore can be used in this runtime.
    - Emulator host always enables Firestore.
    - Otherwise require valid ADC credentials.
    """
    if settings.FIRESTORE_EMULATOR_HOST:
        return True
    try:
        google.auth.default()
        return True
    except DefaultCredentialsError:
        return False
    except Exception as exc:
        logger.debug(f"Failed checking ADC credentials: {exc}")
        return False


def get_eam_service() -> EAMService:
    """Get or create the singleton EAM service instance.

    Tries Firestore first; falls back to in-memory JSON-backed service
    when Firestore is unavailable (no emulator, no GCP credentials).
    """
    global _eam_service
    if _eam_service is not None:
        return _eam_service

    # Try Firestore when emulator or ADC credentials are available.
    if _has_firestore_runtime():
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
