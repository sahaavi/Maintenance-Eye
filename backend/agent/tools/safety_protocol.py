"""
Safety Protocol Tool
ADK tool function for retrieving safety procedures for equipment types.
"""

import logging

from services.firestore_eam import get_eam_service

logger = logging.getLogger("maintenance-eye.tools.safety")

# Fallback safety protocols when nothing found in knowledge base
DEFAULT_SAFETY = {
    "escalator": {
        "ppe": ["Safety boots", "High-visibility vest", "Safety glasses"],
        "loto_required": True,
        "precautions": [
            "Ensure escalator is stopped and LOTO applied before hands-on inspection",
            "Watch for pinch points at handrail entry/exit",
            "Stay clear of comb plates during any movement test",
        ],
    },
    "elevator": {
        "ppe": ["Safety boots", "High-visibility vest", "Hard hat"],
        "loto_required": True,
        "precautions": [
            "Ensure car is secured with LOTO before pit or top-of-car entry",
            "Verify emergency stop is engaged",
            "Follow confined space procedures for pit entry",
        ],
    },
    "switch_machine": {
        "ppe": ["Safety boots", "High-visibility vest", "Hard hat", "Safety glasses"],
        "loto_required": True,
        "precautions": [
            "Coordinate with control center before any switch inspection",
            "Stay clear of moving parts — switch machines actuate with high force",
            "Track-level work requires flagging protection",
        ],
    },
    "default": {
        "ppe": ["Safety boots", "High-visibility vest", "Safety glasses"],
        "loto_required": False,
        "precautions": [
            "Ensure area is safe before starting inspection",
            "Be aware of your surroundings and potential hazards",
            "Follow site-specific safety procedures",
        ],
    },
}


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
    eam = get_eam_service()

    try:
        # Try knowledge base first
        results = await eam.search_knowledge_base(
            query=f"safety protocol {asset_type}",
            asset_type=asset_type,
            department=department,
        )

        if results:
            return {
                "source": "knowledge_base",
                "asset_type": asset_type,
                "protocols": [r.model_dump() for r in results[:3]],
            }

        # Fallback to defaults
        protocol = DEFAULT_SAFETY.get(asset_type, DEFAULT_SAFETY["default"])
        return {
            "source": "default",
            "asset_type": asset_type,
            "ppe_required": protocol["ppe"],
            "loto_required": protocol["loto_required"],
            "precautions": protocol["precautions"],
        }

    except Exception as e:
        logger.error(f"Safety protocol lookup failed: {e}")
        protocol = DEFAULT_SAFETY["default"]
        return {
            "source": "fallback",
            "asset_type": asset_type,
            "ppe_required": protocol["ppe"],
            "loto_required": protocol["loto_required"],
            "precautions": protocol["precautions"],
            "error": str(e),
        }
