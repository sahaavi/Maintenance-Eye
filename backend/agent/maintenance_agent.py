"""
Maintenance-Eye Agent Definition
ADK root agent with tool bindings for maintenance inspection operations.
"""

import logging
from typing import Optional

from google.adk.agents import Agent

from config import settings
from agent.prompts import SYSTEM_PROMPT, CHAT_SYSTEM_PROMPT, AGENT_NAME
from agent.tools.asset_lookup import lookup_asset
from agent.tools.inspection_history import get_inspection_history
from agent.tools.knowledge_search import search_knowledge_base
from agent.tools.work_order import manage_work_order
from agent.tools.safety_protocol import get_safety_protocol
from agent.tools.report_generator import generate_report
from agent.tools.confirm_action import propose_action, check_pending_actions
from agent.tools.smart_search import smart_search

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
            smart_search,
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


def create_chat_agent() -> Agent:
    """
    Create the text-chat variant of the Maintenance-Eye agent.

    Uses GEMINI_MODEL (gemini-2.5-flash) for clean text responses
    instead of the native audio model. Same tools, tailored prompt.
    """
    agent = Agent(
        name=AGENT_NAME,
        model=settings.GEMINI_MODEL,
        description=(
            "AI maintenance co-pilot for text-based chat. Helps technicians "
            "look up assets, analyze photos, manage work orders, and answer "
            "maintenance questions via text."
        ),
        instruction=CHAT_SYSTEM_PROMPT,
        tools=[
            smart_search,
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

    logger.info(f"Created Chat Agent '{AGENT_NAME}' with {len(agent.tools)} tools")
    logger.info(f"  Model: {settings.GEMINI_MODEL}")
    return agent


# Module-level agent instances — used by Runners in main.py
maintenance_agent = create_maintenance_agent()
chat_agent = create_chat_agent()

