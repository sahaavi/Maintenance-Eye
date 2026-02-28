"""
Asset Lookup Tool
ADK tool function for finding assets by name, code, or location.
"""

import asyncio
import logging
from typing import Optional

from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.asset")


def lookup_asset(
    query: str = "",
    asset_id: str = "",
    department: str = "",
    station: str = "",
    asset_type: str = "",
) -> dict:
    """
    Look up a maintenance asset by its ID, name, location, or department.
    Use this tool when the technician mentions a specific piece of equipment,
    a station name, or an asset code.

    Args:
        query: Free text search (asset name, code, or station).
        asset_id: Exact asset ID if known (e.g., "ESC-SC-003").
        department: Filter by department (e.g., "elevating_devices").
        station: Filter by station name (e.g., "Stadium-Chinatown").
        asset_type: Filter by type (e.g., "escalator", "elevator").

    Returns:
        dict with matching asset(s) information including location,
        type, department, last inspection date, and status.
    """
    eam = get_eam_service()

    try:
        if asset_id:
            asset = asyncio.get_event_loop().run_until_complete(
                eam.get_asset(asset_id)
            )
            if asset:
                return {
                    "found": True,
                    "count": 1,
                    "assets": [asset.model_dump()],
                }
            return {"found": False, "count": 0, "assets": [], "message": f"No asset found with ID: {asset_id}"}

        assets = asyncio.get_event_loop().run_until_complete(
            eam.search_assets(
                query=query,
                department=department,
                station=station,
                asset_type=asset_type,
            )
        )
        return {
            "found": len(assets) > 0,
            "count": len(assets),
            "assets": [a.model_dump() for a in assets[:10]],  # Limit results
        }

    except Exception as e:
        logger.error(f"Asset lookup failed: {e}")
        return {"found": False, "count": 0, "assets": [], "error": str(e)}
