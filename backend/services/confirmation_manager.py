"""
Confirmation Manager
Handles human-in-the-loop confirmation for critical agent actions.

Flow:
  1. Agent proposes action (e.g., create work order)  →  PendingAction created
  2. Pending action sent to technician via WebSocket  →  Awaiting confirmation
  3. Technician confirms / rejects / corrects         →  Action executed or discarded
  4. If corrected, correction logged for feedback loop
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger("maintenance-eye.confirmation")

# Python 3.10 compat: datetime.UTC was added in 3.11
_UTC = timezone.utc


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ActionType(str, Enum):
    CREATE_WORK_ORDER = "create_work_order"
    UPDATE_WORK_ORDER = "update_work_order"
    ESCALATE_PRIORITY = "escalate_priority"
    CLOSE_WORK_ORDER = "close_work_order"
    CHANGE_CLASSIFICATION = "change_classification"


class ConfirmationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    EXPIRED = "expired"


class PendingAction(BaseModel):
    """An action proposed by the agent that needs technician confirmation."""

    action_id: str = Field(default_factory=lambda: f"ACT-{uuid.uuid4().hex[:8]}")
    action_type: ActionType
    session_id: str
    asset_id: str = ""
    description: str
    proposed_data: dict = Field(default_factory=dict)
    ai_confidence: float = 0.0
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(tz=_UTC).isoformat())
    resolved_at: str | None = None
    technician_notes: str = ""
    corrections: dict = Field(default_factory=dict)


class ConfirmationResult(BaseModel):
    """Result after technician responds to a pending action."""

    action_id: str
    status: ConfirmationStatus
    corrections: dict = Field(default_factory=dict)
    technician_notes: str = ""


# ---------------------------------------------------------------------------
# Confirmation Manager
# ---------------------------------------------------------------------------


class ConfirmationManager:
    """
    Manages the queue of pending actions per inspection session.

    Thread-safe for asyncio — each session gets its own manager instance.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._pending: dict[str, PendingAction] = {}
        self._history: list[PendingAction] = []

    def propose_action(
        self,
        action_type: ActionType,
        description: str,
        proposed_data: dict,
        ai_confidence: float = 0.0,
        asset_id: str = "",
    ) -> PendingAction:
        """
        The agent proposes a critical action for technician confirmation.
        Returns the PendingAction with a unique action_id.
        """
        action = PendingAction(
            action_type=action_type,
            session_id=self.session_id,
            asset_id=asset_id,
            description=description,
            proposed_data=proposed_data,
            ai_confidence=ai_confidence,
        )
        self._pending[action.action_id] = action
        logger.info(
            f"[{self.session_id}] Proposed: {action.action_type.value} "
            f"({action.action_id}) — confidence {ai_confidence:.0%}"
        )
        return action

    def confirm(self, action_id: str, technician_notes: str = "") -> PendingAction | None:
        """Technician confirms the proposed action."""
        action = self._pending.pop(action_id, None)
        if not action:
            logger.warning(f"Action {action_id} not found or already resolved")
            return None
        action.status = ConfirmationStatus.CONFIRMED
        action.resolved_at = datetime.now(tz=_UTC).isoformat()
        action.technician_notes = technician_notes
        self._history.append(action)
        logger.info(f"[{self.session_id}] Confirmed: {action_id}")
        return action

    def reject(self, action_id: str, technician_notes: str = "") -> PendingAction | None:
        """Technician rejects the proposed action."""
        action = self._pending.pop(action_id, None)
        if not action:
            logger.warning(f"Action {action_id} not found or already resolved")
            return None
        action.status = ConfirmationStatus.REJECTED
        action.resolved_at = datetime.now(tz=_UTC).isoformat()
        action.technician_notes = technician_notes
        self._history.append(action)
        logger.info(f"[{self.session_id}] Rejected: {action_id}")
        return action

    def correct(
        self,
        action_id: str,
        corrections: dict,
        technician_notes: str = "",
    ) -> PendingAction | None:
        """
        Technician corrects the proposed action (e.g., changes EAM codes).
        The corrected data is merged into the proposed data.
        """
        action = self._pending.pop(action_id, None)
        if not action:
            logger.warning(f"Action {action_id} not found or already resolved")
            return None
        action.status = ConfirmationStatus.CORRECTED
        action.resolved_at = datetime.now(tz=_UTC).isoformat()
        action.corrections = corrections
        action.technician_notes = technician_notes
        # Apply corrections to the proposed data
        action.proposed_data.update(corrections)
        self._history.append(action)
        logger.info(f"[{self.session_id}] Corrected: {action_id} — {list(corrections.keys())}")
        return action

    def get_pending(self) -> list[PendingAction]:
        """Get all pending (unresolved) actions."""
        return list(self._pending.values())

    def get_pending_by_id(self, action_id: str) -> PendingAction | None:
        """Get a specific pending action."""
        return self._pending.get(action_id)

    def get_history(self) -> list[PendingAction]:
        """Get all resolved actions (confirmed, rejected, corrected)."""
        return list(self._history)

    def get_stats(self) -> dict:
        """Get summary stats for this session's confirmation workflow."""
        total = len(self._history)
        if total == 0:
            return {
                "total": 0,
                "confirmed": 0,
                "rejected": 0,
                "corrected": 0,
                "pending": len(self._pending),
            }
        confirmed = sum(1 for a in self._history if a.status == ConfirmationStatus.CONFIRMED)
        rejected = sum(1 for a in self._history if a.status == ConfirmationStatus.REJECTED)
        corrected = sum(1 for a in self._history if a.status == ConfirmationStatus.CORRECTED)
        return {
            "total": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "corrected": corrected,
            "pending": len(self._pending),
            "accuracy_rate": round(confirmed / total, 2) if total > 0 else 0,
        }


# ---------------------------------------------------------------------------
# Session registry — one ConfirmationManager per session
# ---------------------------------------------------------------------------

_session_managers: dict[str, ConfirmationManager] = {}


def get_confirmation_manager(session_id: str) -> ConfirmationManager:
    """Get or create a ConfirmationManager for the given session."""
    if session_id not in _session_managers:
        _session_managers[session_id] = ConfirmationManager(session_id)
    return _session_managers[session_id]


def remove_confirmation_manager(session_id: str) -> dict | None:
    """Remove and return stats when a session ends."""
    mgr = _session_managers.pop(session_id, None)
    if mgr:
        return mgr.get_stats()
    return None
