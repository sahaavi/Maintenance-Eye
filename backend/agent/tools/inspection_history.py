"""
Inspection History Tool
ADK tool function for retrieving past inspection records.
"""

from agent.tools.wrapper import tool_wrapper
from services.firestore_eam import get_eam_service
from services.inspection_context import build_inspection_history_context


@tool_wrapper
async def get_inspection_history(
    asset_id: str,
    limit: int = 5,
) -> dict:
    """
    Retrieve past inspection records and related work orders for an asset.
    Use this to check for recurring issues, past failures, and maintenance patterns.

    Args:
        asset_id: The asset ID to get history for (e.g., "ESC-SC-003").
        limit: Maximum number of past inspections to return (default 5).

    Returns:
        dict with inspection history, related work orders, and failure patterns.
    """
    return await build_inspection_history_context(get_eam_service(), asset_id, limit=limit)
