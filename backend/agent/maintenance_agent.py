"""
Maintenance-Eye Agent Definition
ADK root agent with tool bindings for maintenance inspection operations.
"""

import logging
from typing import Optional

from google.adk.agents import Agent

from config import settings
from agent.prompts import SYSTEM_PROMPT, AGENT_NAME
from agent.tools.asset_lookup import lookup_asset
from agent.tools.inspection_history import get_inspection_history
from agent.tools.knowledge_search import search_knowledge_base
from agent.tools.work_order import manage_work_order
from agent.tools.safety_protocol import get_safety_protocol
from agent.tools.report_generator import generate_report
from agent.tools.confirm_action import propose_action, check_pending_actions

logger = logging.getLogger("maintenance-eye.agent")


def create_maintenance_agent() -> Agent:
    """
    Create and configure the Maintenance-Eye ADK Agent.

    The agent ("Max") is a senior maintenance engineer AI co-pilot
    that helps field technicians inspect equipment via phone camera.

    Uses GEMINI_LIVE_MODEL for native audio support in Live API sessions.
    Default: gemini-live-2.5-flash-native-audio (GA)
    """

    agent = Agent(
        name=AGENT_NAME,
        model=settings.GEMINI_LIVE_MODEL,
        description=(
            "AI maintenance co-pilot that helps field technicians inspect "
            "equipment via phone camera, identify issues, classify them using "
            "EAM codes, and create work orders."
        ),
        instruction=SYSTEM_PROMPT,
        tools=[
            lookup_asset,
            get_inspection_history,
            search_knowledge_base,
            manage_work_order,
            get_safety_protocol,
            generate_report,
            propose_action,
            check_pending_actions,
        ],
    )

    logger.info(f"Created Maintenance Agent '{AGENT_NAME}' with {len(agent.tools)} tools")
    logger.info(f"  Model: {settings.GEMINI_LIVE_MODEL}")
    return agent


# Module-level agent instance — used by the Runner in main.py
maintenance_agent = create_maintenance_agent()

