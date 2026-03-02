"""
Asset Lookup Tool
ADK tool function for finding assets by name, code, or location.
"""

import logging

from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.asset")


from agent.tools.wrapper import tool_wrapper

@tool_wrapper
async def lookup_asset(
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

    The query supports partial word matching — each word in the query is matched
    independently against asset name, ID, type, department, station, manufacturer,
    model, and hierarchy. For example, "Gateway HVAC" will match "Gateway Hvac Unit #2".

    If the first search returns no results, try broadening the query:
    - Remove department filter and search by name only
    - Use fewer words (e.g., "HVAC Gateway" instead of "Gateway HVAC Unit #2")
    - Try searching by station name alone

    Args:
        query: Free text search — each word is matched independently across
               asset name, ID, type, station, manufacturer, model, and hierarchy.
        asset_id: Exact asset ID if known (e.g., "ESC-SC-003").
        department: Filter by department (e.g., "elevating_devices"). Leave empty
                    if unsure — the search will find the asset across all departments.
        station: Filter by station name (e.g., "Stadium-Chinatown").
        asset_type: Filter by type (e.g., "escalator", "elevator", "hvac_unit").

    Returns:
        dict with matching asset(s) information including location,
        type, department, last inspection date, and status.
    """
    eam = get_eam_service()

    try:
        if asset_id:
            asset = await eam.get_asset(asset_id)
            if asset:
                return {
                    "found": True,
                    "count": 1,
                    "assets": [asset.model_dump()],
                }
            return {"found": False, "count": 0, "assets": [], "message": f"No asset found with ID: {asset_id}"}

        assets = await eam.search_assets(
            query=query,
            department=department,
            station=station,
            asset_type=asset_type,
        )
        return {
            "found": len(assets) > 0,
            "count": len(assets),
            "assets": [a.model_dump() for a in assets[:10]],  # Limit results
        }

    except Exception as e:
        logger.error(f"Asset lookup failed: {e}")
        return {"found": False, "count": 0, "assets": [], "error": str(e)}
