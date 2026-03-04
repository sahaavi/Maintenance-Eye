"""
EAM Service Interface — Abstraction Layer
Defines the abstract interface for Enterprise Asset Management operations.
Hackathon uses FirestoreEAM; production would swap in HexagonEAM.
"""

from abc import ABC, abstractmethod
from typing import Optional

from models.schemas import (
    Asset,
    WorkOrder,
    WorkOrderStatus,
    EAMCode,
    InspectionRecord,
    KnowledgeBaseEntry,
    CorrectionLog,
)


class EAMService(ABC):
    """
    Abstract base class for Enterprise Asset Management operations.
    
    Implementations:
    - FirestoreEAM: Uses Firestore with synthetic data (hackathon)
    - HexagonEAM: Connects to real Hexagon EAM API (production)
    """

    # --- Asset Operations ---
    @abstractmethod
    async def get_asset(self, asset_id: str) -> Optional[Asset]:
        """Look up an asset by its ID."""
        ...

    @abstractmethod
    async def search_assets(
        self,
        query: str = "",
        department: str = "",
        station: str = "",
        asset_type: str = "",
    ) -> list[Asset]:
        """Search assets by name, department, station, or type."""
        ...

    # --- Work Order Operations ---
    @abstractmethod
    async def get_work_order(self, wo_id: str) -> Optional[WorkOrder]:
        """Look up a single work order by its ID."""
        ...

    @abstractmethod
    async def create_work_order(self, work_order: WorkOrder) -> WorkOrder:
        """Create a new work order and return it with generated ID."""
        ...

    @abstractmethod
    async def update_work_order(
        self, wo_id: str, updates: dict
    ) -> Optional[WorkOrder]:
        """Update an existing work order."""
        ...

    @abstractmethod
    async def get_work_orders(
        self,
        asset_id: str = "",
        status: Optional[WorkOrderStatus] = None,
    ) -> list[WorkOrder]:
        """Get work orders, optionally filtered by asset and status."""
        ...

    @abstractmethod
    async def search_work_orders(
        self,
        q: str = "",
        priority: str = "",
        department: str = "",
        status: Optional[WorkOrderStatus] = None,
        location: str = "",
    ) -> list[WorkOrder]:
        """Search work orders with full-text query across wo_id, description,
        asset_id, and EAM codes. Supports priority, department, status, and
        location (resolved via asset join) filters."""
        ...

    @abstractmethod
    async def get_locations(self) -> list[dict]:
        """Return unique stations derived from assets.
        Each dict has: station, station_code, zone, asset_count."""
        ...

    # --- EAM Code Operations ---
    @abstractmethod
    async def get_eam_codes(
        self,
        code_type: str = "",
        department: str = "",
        asset_type: str = "",
    ) -> list[EAMCode]:
        """Get EAM classification codes, optionally filtered."""
        ...

    # --- Inspection Operations ---
    @abstractmethod
    async def save_inspection(self, inspection: InspectionRecord) -> InspectionRecord:
        """Save a completed inspection record."""
        ...

    @abstractmethod
    async def get_inspection_history(
        self, asset_id: str, limit: int = 10
    ) -> list[InspectionRecord]:
        """Get past inspections for an asset."""
        ...

    # --- Knowledge Base ---
    @abstractmethod
    async def search_knowledge_base(
        self, query: str, asset_type: str = "", department: str = ""
    ) -> list[KnowledgeBaseEntry]:
        """Search maintenance knowledge base."""
        ...

    # --- Feedback Loop ---
    @abstractmethod
    async def log_correction(self, correction: CorrectionLog) -> None:
        """Log a technician's correction to AI classification."""
        ...

    @abstractmethod
    async def get_corrections(
        self, asset_id: str = "", code_type: str = ""
    ) -> list[CorrectionLog]:
        """Get past corrections for learning context."""
        ...
