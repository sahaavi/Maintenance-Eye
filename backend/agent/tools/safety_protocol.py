"""
Safety Protocol Tool
ADK tool function for retrieving safety procedures for equipment types.
"""

from agent.tools.wrapper import tool_wrapper
from services.firestore_eam import get_eam_service
from services.inspection_context import build_safety_protocol_context


@tool_wrapper
async def get_safety_protocol(
    asset_type: str,
    department: str = "",
) -> dict:
    """
    Get safety protocols and PPE requirements for inspecting a specific
    type of equipment. ALWAYS call this before starting an inspection.

    Args:
        asset_type: Type of equipment (e.g., "escalator", "elevator", "switch_machine").
        department: Department the asset belongs to.

    Returns:
        dict with PPE requirements, LOTO status, and safety precautions.
    """
    return await build_safety_protocol_context(
        get_eam_service(),
        asset_type=asset_type,
        department=department,
    )
