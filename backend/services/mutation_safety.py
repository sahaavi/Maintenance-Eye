"""
Executable mutation safety policy for technician-facing actions.

Prompt instructions can guide the model, but this module owns the backend
decision about which mutations require technician confirmation.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar

CREATE_WORK_ORDER = "create_work_order"
UPDATE_WORK_ORDER = "update_work_order"
ESCALATE_PRIORITY = "escalate_priority"
CLOSE_WORK_ORDER = "close_work_order"
CHANGE_CLASSIFICATION = "change_classification"

_confirmed_action_type: ContextVar[str | None] = ContextVar(
    "maintenance_eye_confirmed_action_type",
    default=None,
)

_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    CREATE_WORK_ORDER: ("asset_id", "description"),
    UPDATE_WORK_ORDER: ("wo_id",),
    ESCALATE_PRIORITY: ("wo_id", "priority"),
    CLOSE_WORK_ORDER: ("wo_id",),
    CHANGE_CLASSIFICATION: ("asset_id",),
}

_WORK_ORDER_MUTATION_ACTION_TYPES: dict[str, tuple[str, ...]] = {
    "create": (CREATE_WORK_ORDER,),
    "update": (UPDATE_WORK_ORDER, ESCALATE_PRIORITY, CLOSE_WORK_ORDER),
}


@contextmanager
def confirmed_mutation(action_type: str) -> Iterator[None]:
    """Temporarily mark the current async context as executing a confirmed action."""
    token = _confirmed_action_type.set(action_type)
    try:
        yield
    finally:
        _confirmed_action_type.reset(token)


def missing_required_fields(action_type: str, fields: Mapping[str, object]) -> list[str]:
    """Return missing required fields for a confirmation action type."""
    missing: list[str] = []
    for field in _REQUIRED_FIELDS.get(action_type, ()):
        value = fields.get(field)
        if not (str(value or "").strip()):
            missing.append(field)
    return missing


def confirmation_action_type_for_work_order_action(action: str) -> str | None:
    """Return the primary confirmation action type for a work-order tool action."""
    action_types = _WORK_ORDER_MUTATION_ACTION_TYPES.get(action)
    return action_types[0] if action_types else None


def work_order_mutation_requires_confirmation(action: str) -> bool:
    """Return whether a manage_work_order action mutates technician-visible state."""
    return action in _WORK_ORDER_MUTATION_ACTION_TYPES


def work_order_mutation_allowed(action: str) -> bool:
    """Return whether the current context may execute this work-order mutation."""
    confirmed_action = _confirmed_action_type.get()
    return confirmed_action in _WORK_ORDER_MUTATION_ACTION_TYPES.get(action, ())


def confirmation_required_response(action: str) -> dict:
    """Build the standard response for an unconfirmed work-order mutation attempt."""
    action_type = confirmation_action_type_for_work_order_action(action)
    label = action.replace("_", " ")
    return {
        "success": False,
        "error": f"Technician confirmation required before {label} work order.",
        "requires_confirmation": True,
        "action_type": action_type,
    }
