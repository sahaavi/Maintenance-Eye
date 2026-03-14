"""
Base EAM Service — shared helpers for JsonEAM and FirestoreEAM.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from models.schemas import Priority, WorkOrderStatus
from services.eam_interface import EAMService


class BaseEAMService(EAMService):
    """
    Base implementation providing shared utility methods for EAM services.
    Subclasses (JsonEAM, FirestoreEAM) provide storage-specific operations
    but delegate text matching, filter resolution, and aggregation here.
    """

    def normalize_work_order_updates(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Normalize enum values in work order updates."""
        normalized_updates = dict(updates)
        if "status" in normalized_updates:
            value = normalized_updates["status"]
            normalized_updates["status"] = (
                value.value
                if isinstance(value, WorkOrderStatus)
                else WorkOrderStatus(str(value).lower()).value
            )
        if "priority" in normalized_updates:
            value = normalized_updates["priority"]
            normalized_updates["priority"] = (
                value.value if isinstance(value, Priority) else Priority(str(value).upper()).value
            )
        return normalized_updates

    # --- Shared search helpers ---

    # Words that describe document type, not content — strip from KB queries
    _KB_META_WORDS = frozenset(
        {
            "protocol",
            "procedure",
            "manual",
            "guide",
            "guidelines",
            "standard",
            "standards",
            "document",
            "checklist",
            "instructions",
            "handbook",
            "specification",
            "reference",
            "sop",
        }
    )

    @staticmethod
    def build_asset_searchable(asset: dict) -> str:
        """Build a searchable string from asset fields (11-field join)."""
        loc = asset.get("location", {})
        return " ".join(
            [
                asset.get("name", ""),
                asset.get("asset_id", ""),
                asset.get("type", ""),
                asset.get("department", ""),
                asset.get("equipment_code", ""),
                asset.get("manufacturer", ""),
                asset.get("model", ""),
                loc.get("station", "") if isinstance(loc, dict) else "",
                loc.get("station_code", "") if isinstance(loc, dict) else "",
                loc.get("zone", "") if isinstance(loc, dict) else "",
                " ".join(asset.get("asset_hierarchy", [])),
            ]
        ).lower()

    @staticmethod
    def build_wo_searchable(wo: dict, asset: dict) -> str:
        """Build a searchable string from work order + asset fields (10-field join)."""
        return " ".join(
            [
                wo.get("wo_id", "") or "",
                wo.get("description", "") or "",
                wo.get("asset_id", "") or "",
                asset.get("name", "") or "",
                asset.get("location", {}).get("station", "")
                if isinstance(asset.get("location"), dict)
                else "",
                wo.get("problem_code", "") or "",
                wo.get("fault_code", "") or "",
                wo.get("action_code", "") or "",
                wo.get("assigned_to", "") or "",
                wo.get("equipment_id", "") or "",
            ]
        ).lower()

    @staticmethod
    def resolve_location_dept_filters(
        assets_iter: Iterator[dict],
        location: str = "",
        department: str = "",
    ) -> tuple[set[str] | None, set[str] | None]:
        """Resolve location/department to asset_id sets from an asset iterator."""
        location_asset_ids: set[str] | None = None
        dept_asset_ids: set[str] | None = None
        if not location and not department:
            return None, None

        loc_lower = location.lower() if location else ""
        location_ids: set[str] = set()
        dept_ids: set[str] = set()

        for a in assets_iter:
            aid = a.get("asset_id", "")
            if department and a.get("department") == department:
                dept_ids.add(aid)
            if location and loc_lower in a.get("location", {}).get("station", "").lower():
                location_ids.add(aid)
            elif not location:
                location_ids.add(aid)

        if location:
            location_asset_ids = location_ids
        if department:
            dept_asset_ids = dept_ids

        return location_asset_ids, dept_asset_ids

    @staticmethod
    def aggregate_stations(assets_iter: Iterator[dict]) -> list[dict]:
        """Aggregate assets into unique station records with counts."""
        stations: dict[str, dict] = {}
        for a in assets_iter:
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

    @classmethod
    def tokenize_kb_query(cls, query: str) -> list[str]:
        """Tokenize and strip meta-words from a KB query."""
        return [
            t for t in re.findall(r"[a-zA-Z0-9]+", query.lower()) if t not in cls._KB_META_WORDS
        ]

    @staticmethod
    def kb_tokens_match(query_tokens: list[str], searchable: str) -> bool:
        """Check if all KB query tokens appear in searchable text."""
        return all(token in searchable for token in query_tokens)
