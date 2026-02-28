"""
Maintenance-Eye Data Models
Pydantic models for assets, work orders, inspections, and EAM codes.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Department(str, Enum):
    ROLLING_STOCK = "rolling_stock"
    GUIDEWAY = "guideway"
    POWER = "power"
    SIGNAL_TELECOM = "signal_telecom"
    FACILITIES = "facilities"
    ELEVATING_DEVICES = "elevating_devices"


class Priority(str, Enum):
    P1_CRITICAL = "P1"
    P2_HIGH = "P2"
    P3_MEDIUM = "P3"
    P4_LOW = "P4"
    P5_PLANNED = "P5"


class WorkOrderStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssetStatus(str, Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUT_OF_SERVICE = "out_of_service"
    DECOMMISSIONED = "decommissioned"


class EAMCodeType(str, Enum):
    PROBLEM = "problem_code"
    FAULT = "fault_code"
    ACTION = "action_code"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class GeoLocation(BaseModel):
    lat: float
    lng: float


class AssetLocation(BaseModel):
    station: str
    station_code: str
    zone: str
    gps: Optional[GeoLocation] = None


# ---------------------------------------------------------------------------
# Core Models
# ---------------------------------------------------------------------------

class Asset(BaseModel):
    """Represents a physical equipment asset in the transit system."""
    asset_id: str
    name: str
    type: str
    department: Department
    location: AssetLocation
    equipment_code: str
    manufacturer: str
    model: str
    install_date: str
    asset_hierarchy: list[str]
    last_inspection: Optional[str] = None
    status: AssetStatus = AssetStatus.OPERATIONAL


class WorkOrder(BaseModel):
    """Represents a maintenance work order in the EAM system."""
    wo_id: str
    asset_id: str
    status: WorkOrderStatus = WorkOrderStatus.OPEN
    priority: Priority = Priority.P3_MEDIUM
    problem_code: str
    fault_code: str
    action_code: str
    failure_class: str
    description: str
    created_by: str = "maintenance-eye-agent"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    assigned_to: Optional[str] = None
    photos: list[str] = Field(default_factory=list)
    ai_confidence: float = 0.0
    technician_confirmed: bool = False
    notes: list[str] = Field(default_factory=list)


class EAMCode(BaseModel):
    """EAM classification code (Problem, Fault, or Action)."""
    code_type: EAMCodeType
    code: str
    label: str
    department: Department
    asset_types: list[str]
    description: str
    related_codes: list[str] = Field(default_factory=list)
    hexagon_mapping: Optional[str] = None


class InspectionRecord(BaseModel):
    """Record of a completed inspection."""
    inspection_id: str
    asset_id: str
    inspector: str
    date: str
    findings: list[InspectionFinding] = Field(default_factory=list)
    overall_condition: str
    next_inspection_due: Optional[str] = None
    work_orders_created: list[str] = Field(default_factory=list)


class InspectionFinding(BaseModel):
    """A single finding within an inspection."""
    finding_id: str
    description: str
    severity: Priority
    problem_code: str
    fault_code: str
    photo_url: Optional[str] = None
    ai_confidence: float = 0.0
    technician_confirmed: bool = False


class KnowledgeBaseEntry(BaseModel):
    """Maintenance knowledge base document."""
    doc_id: str
    title: str
    asset_types: list[str]
    department: Department
    content: str
    tags: list[str] = Field(default_factory=list)
    source: str


class CorrectionLog(BaseModel):
    """Log of technician corrections to AI classifications (feedback loop)."""
    correction_id: str
    asset_id: str
    original_code: str
    corrected_code: str
    code_type: EAMCodeType
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    technician: str


# Fix forward reference
InspectionRecord.model_rebuild()
