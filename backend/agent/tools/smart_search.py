"""
Smart Search Tool
Unified ADK tool that wraps the QueryEngine for natural language search
across work orders, assets, locations, EAM codes, and knowledge base.
"""

import logging

from agent.tools.wrapper import tool_wrapper
from services.firestore_eam import get_eam_service
from services.search_service import SearchService

logger = logging.getLogger("maintenance-eye.tools.smart_search")

_search_service = SearchService()


@tool_wrapper
async def smart_search(
    query: str,
    search_type: str = "auto",
    limit: int = 10,
) -> dict:
    """
    Search across work orders, assets, locations, EAM codes, and knowledge base
    using natural language. This is the primary search tool — use it when the
    technician asks to find something and you're not sure which specific tool to use.

    Accepts short, informal input and automatically:
    - Detects what the user is looking for (work order, asset, location, etc.)
    - Normalizes IDs (e.g., "wo 10234" → "WO-2025-10234")
    - Maps aliases (e.g., "critical" → P1, "rolling stock" → rolling_stock department)
    - Expands synonyms (e.g., "vibration" also searches "noise", "shaking")
    - Ranks results by relevance

    Args:
        query: Natural language search query. Examples:
            - "wo 10234" — find a specific work order
            - "pump vibration" — find assets or work orders about pump vibration
            - "P1 open rolling stock" — find critical open work orders in rolling stock
            - "escalator stadium" — find escalators at Stadium-Chinatown station
            - "safety lockout procedure" — find safety procedures in knowledge base
            - "ESC-SC-003" — look up a specific asset by ID
        search_type: Hint for what to search. One of:
            - "auto" (default) — automatically detect from query
            - "work_order" — search only work orders
            - "asset" — search only assets
            - "location" — search locations/stations
            - "eam_code" — search EAM classification codes
            - "knowledge" — search knowledge base
        limit: Maximum number of results to return (default 10).

    Returns:
        dict with:
        - intent: what the engine determined the user is looking for
        - confidence: how confident the engine is in the intent (0-1)
        - total: number of results found
        - results: list of ranked results, each with score, type, and data
        - search_metadata: normalization details for transparency
        - optional confirmation hints when malformed asset IDs are detected:
          `needs_asset_confirmation`, `guessed_assets`, `no_asset_match`
    """
    eam = get_eam_service()

    try:
        return await _search_service.smart_search(
            eam,
            query=query,
            search_type=search_type,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"Smart search failed: {e}", exc_info=True)
        return {
            "success": False,
            "intent": "error",
            "confidence": 0,
            "total": 0,
            "has_results": False,
            "results": [],
            "error": str(e),
        }
