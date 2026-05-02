from __future__ import annotations

import inspect

import pytest
from api import routes  # type: ignore[import-not-found]
from services.confirmation_manager import (  # type: ignore[import-not-found]
    ActionType,
    get_confirmation_manager,
)


def test_confirmation_routes_use_workflow_interface() -> None:
    confirm_source = inspect.getsource(routes.confirm_action)
    correct_source = inspect.getsource(routes.correct_action)

    assert "api.websocket" not in confirm_source
    assert "api.websocket" not in correct_source
    assert "ConfirmationWorkflow" in confirm_source
    assert "ConfirmationWorkflow" in correct_source


@pytest.mark.integration
@pytest.mark.api
def test_confirmation_http_flow_confirm(client) -> None:
    session_id = "integration-session-1"
    manager = get_confirmation_manager(session_id)
    proposed = manager.propose_action(
        action_type=ActionType.CREATE_WORK_ORDER,
        description="Create WO for crack",
        proposed_data={"priority": "P1", "asset_id": "AST-UNIT-001"},
        ai_confidence=0.95,
    )

    pending = client.get(f"/api/sessions/{session_id}/pending")
    assert pending.status_code == 200
    assert pending.json()["pending_count"] == 1

    confirm = client.post(
        f"/api/sessions/{session_id}/confirm/{proposed.action_id}", params={"notes": "confirmed"}
    )
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["status"] == "confirmed"
    assert body["action"]["technician_notes"] == "confirmed"


@pytest.mark.integration
@pytest.mark.api
def test_confirmation_http_flow_correct(client) -> None:
    session_id = "integration-session-2"
    manager = get_confirmation_manager(session_id)
    proposed = manager.propose_action(
        action_type=ActionType.CHANGE_CLASSIFICATION,
        description="Adjust EAM code",
        proposed_data={"problem_code": "ME-003", "priority": "P3"},
        ai_confidence=0.6,
    )

    corrections = {"problem_code": "EL-101", "priority": "P2"}
    response = client.post(
        f"/api/sessions/{session_id}/correct/{proposed.action_id}",
        params={"notes": "field correction"},
        json=corrections,
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["status"] == "corrected"
    assert action["proposed_data"]["problem_code"] == "EL-101"
