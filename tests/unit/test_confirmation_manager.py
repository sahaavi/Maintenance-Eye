from __future__ import annotations

from services.confirmation_manager import (  # type: ignore[import-not-found]
    ActionType,
    ConfirmationStatus,
    get_confirmation_manager,
    remove_confirmation_manager,
)


def test_confirmation_manager_propose_confirm_flow() -> None:
    manager = get_confirmation_manager("session-unit-1")
    proposed = manager.propose_action(
        action_type=ActionType.CREATE_WORK_ORDER,
        description="Create WO for corrosion",
        proposed_data={"priority": "P2"},
        ai_confidence=0.91,
        asset_id="AST-UNIT-001",
    )

    assert proposed.status == ConfirmationStatus.PENDING
    assert len(manager.get_pending()) == 1

    confirmed = manager.confirm(proposed.action_id, "approved")
    assert confirmed is not None
    assert confirmed.status == ConfirmationStatus.CONFIRMED
    assert confirmed.technician_notes == "approved"
    assert manager.get_stats()["confirmed"] == 1

    remove_confirmation_manager("session-unit-1")


def test_confirmation_manager_correction_merges_payload() -> None:
    manager = get_confirmation_manager("session-unit-2")
    proposed = manager.propose_action(
        action_type=ActionType.CHANGE_CLASSIFICATION,
        description="Adjust fault code",
        proposed_data={"fault_code": "WEAR-SUR", "priority": "P3"},
        ai_confidence=0.76,
    )

    corrected = manager.correct(proposed.action_id, {"fault_code": "ALIGN-MIS", "priority": "P2"})
    assert corrected is not None
    assert corrected.status == ConfirmationStatus.CORRECTED
    assert corrected.proposed_data["fault_code"] == "ALIGN-MIS"
    assert corrected.proposed_data["priority"] == "P2"

    stats = manager.get_stats()
    assert stats["corrected"] == 1
    assert stats["pending"] == 0

    remove_confirmation_manager("session-unit-2")
