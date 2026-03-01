"""
Knowledge Base Search Tool
ADK tool function for searching maintenance procedures and documentation.
"""

import logging

from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.knowledge")


async def search_knowledge_base(
    query: str,
    asset_type: str = "",
    department: str = "",
) -> dict:
    """
    Search the maintenance knowledge base for repair procedures,
    troubleshooting guides, safety protocols, and OEM documentation.

    Args:
        query: Search query (e.g., "escalator handrail wear", "switch machine alignment").
        asset_type: Filter by asset type (e.g., "escalator", "switch_machine").
        department: Filter by department (e.g., "elevating_devices", "guideway").

    Returns:
        dict with matching knowledge base entries including procedures and manuals.
    """
    eam = get_eam_service()

    try:
        results = await eam.search_knowledge_base(
            query=query, asset_type=asset_type, department=department
        )
        return {
            "found": len(results) > 0,
            "count": len(results),
            "entries": [r.model_dump() for r in results[:5]],
        }

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}")
        return {"found": False, "count": 0, "entries": [], "error": str(e)}
