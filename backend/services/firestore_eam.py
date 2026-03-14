"""
Firestore EAM Implementation
Implements the EAM service interface using Google Cloud Firestore
with synthetic data for the hackathon.
"""

import logging
from datetime import datetime

import google.auth
from config import settings
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import firestore
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
from services.eam_interface import EAMService
from services.search_matcher import query_matches_text

logger = logging.getLogger("maintenance-eye.firestore")


class FirestoreEAM(BaseEAMService):
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
            logger.info(f"Using Firestore emulator at {settings.FIRESTORE_EMULATOR_HOST}")
        else:
            logger.info("Using Cloud Firestore")

    # --- Asset Operations ---

    async def get_asset(self, asset_id: str) -> Asset | None:
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
            if station and station.lower() not in asset.location.station.lower():
                continue
            if query:
                searchable = self.build_asset_searchable(data)
                if not query_matches_text(query, searchable):
                    continue
            results.append(asset)
        return results

    # --- Work Order Operations ---

    async def get_work_order(self, wo_id: str) -> WorkOrder | None:
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

    async def update_work_order(self, wo_id: str, updates: dict) -> WorkOrder | None:
        ref = self.db.collection("work_orders").document(wo_id)
        doc = await ref.get()
        if not doc.exists:
            return None
        normalized_updates = self.normalize_work_order_updates(updates)
        await ref.update(normalized_updates)
        updated_doc = await ref.get()
        return WorkOrder(**updated_doc.to_dict())

    async def get_work_orders(
        self,
        asset_id: str = "",
        status: WorkOrderStatus | None = None,
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
        status: WorkOrderStatus | None = None,
        location: str = "",
    ) -> list[WorkOrder]:
        ref = self.db.collection("work_orders")
        if status:
            ref = ref.where(filter=firestore.FieldFilter("status", "==", status.value))
        if priority:
            ref = ref.where(filter=firestore.FieldFilter("priority", "==", priority.upper()))

        # Pre-resolve location/department to asset_id sets via shared helper
        location_asset_ids: set[str] | None = None
        dept_asset_ids: set[str] | None = None
        if location or department:
            asset_ref = self.db.collection("assets")
            if department:
                asset_ref = asset_ref.where(
                    filter=firestore.FieldFilter("department", "==", department)
                )
            filter_assets = []
            async for doc in asset_ref.stream():
                filter_assets.append(doc.to_dict())
            location_asset_ids, dept_asset_ids = self.resolve_location_dept_filters(
                iter(filter_assets), location, department
            )

        # Fetch all assets for joining/enriching the search results
        asset_map = {}
        async for doc in self.db.collection("assets").stream():
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
                searchable = self.build_wo_searchable(wo, asset)
                if not query_matches_text(q, searchable):
                    continue
            results.append(WorkOrder(**wo))
        return results

    async def get_locations(self) -> list[dict]:
        assets = []
        async for doc in self.db.collection("assets").stream():
            assets.append(doc.to_dict())
        return self.aggregate_stations(iter(assets))

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
                logger.warning(
                    f"Inspection history index missing for {asset_id}, falling back to unordered search: {e}"
                )
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

    async def search_knowledge_base(
        self, query: str, asset_type: str = "", department: str = ""
    ) -> list[KnowledgeBaseEntry]:
        ref = self.db.collection("knowledge_base")
        if department:
            ref = ref.where(filter=firestore.FieldFilter("department", "==", department))

        query_tokens = self.tokenize_kb_query(query) if query else []

        docs = ref.stream()
        results = []
        async for doc in docs:
            entry = KnowledgeBaseEntry(**doc.to_dict())
            if asset_type and asset_type not in entry.asset_types:
                continue
            if query_tokens:
                searchable = f"{entry.title} {entry.content} {' '.join(entry.tags)}".lower()
                if not self.kb_tokens_match(query_tokens, searchable):
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
        logger.info(f"Logged correction: {correction.original_code} → {correction.corrected_code}")

    async def get_corrections(self, asset_id: str = "", code_type: str = "") -> list[CorrectionLog]:
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
_eam_service: EAMService | None = None


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
