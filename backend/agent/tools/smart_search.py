"""
Smart Search Tool
Unified ADK tool that wraps the QueryEngine for natural language search
across work orders, assets, locations, EAM codes, and knowledge base.
"""

import logging

from services.firestore_eam import get_eam_service
from services.query_engine import QueryEngine, SearchIntent

logger = logging.getLogger("maintenance-eye.tools.smart_search")

_engine = QueryEngine()


from agent.tools.wrapper import tool_wrapper


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
        parsed = _engine.build_query(query)

        # Override intent if user specified search_type
        if search_type != "auto":
            try:
                parsed.intent = SearchIntent(search_type)
            except ValueError:
                pass

        result = await _engine.execute_search(parsed, eam, limit=limit)

        # Format results for the agent
        formatted_results = []
        for scored_item in result.items:
            item = scored_item.item
            entry = {
                "score": round(scored_item.score, 2),
                "type": scored_item.entity_type,
                "match": scored_item.match_type,
            }
            if hasattr(item, "model_dump"):
                entry["data"] = item.model_dump()
            elif isinstance(item, dict):
                entry["data"] = item
            else:
                entry["data"] = str(item)
            formatted_results.append(entry)

        response = {
            "success": True,
            "intent": parsed.intent.value,
            "confidence": round(parsed.confidence, 2),
            "total": result.total,
            "has_results": result.total > 0,
            "results": formatted_results,
            "search_metadata": {
                "raw_input": parsed.raw_input,
                "normalized_terms": parsed.normalized_terms,
                "extracted_ids": parsed.extracted_ids,
                "filters": parsed.filters,
                "expanded_terms": parsed.expanded_terms,
                "search_time_ms": result.search_time_ms,
            },
        }

        if result.total == 0 and parsed.intent in {
            SearchIntent.work_order,
            SearchIntent.asset,
            SearchIntent.auto,
        }:
            hints = QueryEngine.extract_asset_hints(query)
            suggestions = await _engine.suggest_asset_candidates(query, eam, limit=3)
            if suggestions:
                suggestion_ids = ", ".join(s["asset_id"] for s in suggestions)
                hinted = ", ".join(hints) if hints else "that asset ID"
                response.update(
                    {
                        "needs_asset_confirmation": True,
                        "attempted_asset_hints": hints,
                        "guessed_assets": suggestions,
                        "message": (
                            f"No records found for {hinted}. Did you mean {suggestion_ids}?"
                        ),
                    }
                )
            elif hints:
                hinted = ", ".join(hints)
                response.update(
                    {
                        "no_asset_match": True,
                        "attempted_asset_hints": hints,
                        "message": (
                            f"No asset found matching {hinted}. "
                            "Ask the user to confirm the exact asset tag."
                        ),
                    }
                )

        return response

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
