from __future__ import annotations

import re

import pytest
from agent.prompts import CHAT_SYSTEM_PROMPT, SYSTEM_PROMPT  # type: ignore[import-not-found]
from agent.tools.confirm_action import (  # type: ignore[import-not-found]
    check_pending_actions,
    propose_action,
    set_session_context,
)


@pytest.mark.ai
def test_prompt_contains_confirmation_gate_requirements() -> None:
    assert "MUST use the `propose_action` tool" in SYSTEM_PROMPT
    assert "WAIT" in SYSTEM_PROMPT
    assert "NEVER skip confirmation" in SYSTEM_PROMPT


@pytest.mark.ai
def test_prompt_bias_coverage_for_all_departments() -> None:
    expected_departments = [
        "Rolling Stock",
        "Guideway",
        "Power",
        "Signal & Telecommunication",
        "Facilities",
        "Elevating Devices",
    ]
    for department in expected_departments:
        assert department in SYSTEM_PROMPT


@pytest.mark.ai
def test_inference_consistency_for_repeated_same_action() -> None:
    set_session_context("ai-session-consistency")
    first = propose_action(
        action_type="create_work_order",
        description="Create work order for repeated vibration issue",
        asset_id="AST-UNIT-001",
        problem_code="ME-003",
        fault_code="WEAR-SUR",
        action_code="REPAIR",
        priority="P2",
        confidence=0.88,
    )
    second = propose_action(
        action_type="create_work_order",
        description="Create work order for repeated vibration issue",
        asset_id="AST-UNIT-001",
        problem_code="ME-003",
        fault_code="WEAR-SUR",
        action_code="REPAIR",
        priority="P2",
        confidence=0.88,
    )

    assert first["success"] and second["success"]
    assert first["confirmation_prompt"]["message"] == second["confirmation_prompt"]["message"]
    assert first["action_id"] != second["action_id"]


@pytest.mark.ai
def test_prompt_robustness_includes_short_field_response_constraints() -> None:
    sentence_count = len([s for s in re.split(r"[.!?]", CHAT_SYSTEM_PROMPT) if s.strip()])
    assert sentence_count >= 8
    assert "Use bullet points" in CHAT_SYSTEM_PROMPT


@pytest.mark.ai
def test_failure_mode_invalid_action_type_returns_controlled_error() -> None:
    set_session_context("ai-session-failure")
    result = propose_action(
        action_type="drop_database",
        description="Invalid action should fail",
    )
    assert result["success"] is False
    assert "Invalid action_type" in result["error"]


@pytest.mark.ai
def test_pending_action_monitoring_surface() -> None:
    set_session_context("ai-session-monitor")
    propose_action(
        action_type="create_work_order",
        description="Create WO for oil leak",
        asset_id="AST-UNIT-002",
        confidence=0.92,
    )
    pending = check_pending_actions()
    assert pending["pending_count"] >= 1
    assert "session_stats" in pending
