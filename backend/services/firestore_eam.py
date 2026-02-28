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
            ref = ref.where("department", "==", department)
        if asset_type:
            ref = ref.where("type", "==", asset_type)

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
        # Generate WO ID
        counter_ref = self.db.collection("_counters").document("work_orders")
        counter_doc = await counter_ref.get()
        if counter_doc.exists:
            count = counter_doc.to_dict().get("count", 0) + 1
        else:
            count = 1
        await counter_ref.set({"count": count})

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
        await ref.update(updates)
        updated_doc = await ref.get()
        return WorkOrder(**updated_doc.to_dict())

    async def get_work_orders(
        self,
        asset_id: str = "",
        status: Optional[WorkOrderStatus] = None,
    ) -> list[WorkOrder]:
        ref = self.db.collection("work_orders")
        if asset_id:
            ref = ref.where("asset_id", "==", asset_id)
        if status:
            ref = ref.where("status", "==", status.value)

        docs = ref.stream()
        results = []
        async for doc in docs:
            results.append(WorkOrder(**doc.to_dict()))
        return results

    # --- EAM Code Operations ---

    async def get_eam_codes(
        self,
        code_type: str = "",
        department: str = "",
        asset_type: str = "",
    ) -> list[EAMCode]:
        ref = self.db.collection("eam_codes")
        if code_type:
            ref = ref.where("code_type", "==", code_type)
        if department:
            ref = ref.where("department", "==", department)

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
            .where("asset_id", "==", asset_id)
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
            ref = ref.where("department", "==", department)

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
            ref = ref.where("asset_id", "==", asset_id)
        if code_type:
            ref = ref.where("code_type", "==", code_type)

        docs = ref.stream()
        results = []
        async for doc in docs:
            results.append(CorrectionLog(**doc.to_dict()))
        return results


# Singleton instance
_eam_service: Optional[FirestoreEAM] = None


def get_eam_service() -> FirestoreEAM:
    """Get or create the singleton EAM service instance."""
    global _eam_service
    if _eam_service is None:
        _eam_service = FirestoreEAM()
    return _eam_service
