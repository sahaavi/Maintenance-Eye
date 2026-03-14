from __future__ import annotations

from typing import Any

import pytest
from models.schemas import WorkOrderStatus  # type: ignore[import-not-found]
from services.firestore_eam import FirestoreEAM  # type: ignore[import-not-found]


class _FakeDoc:
    def __init__(self, data: dict[str, Any]):
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return self._data


class _FakeAsyncStream:
    def __init__(self, docs: list[dict[str, Any]]):
        self._docs = docs
        self._index = 0

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self):
        if self._index >= len(self._docs):
            raise StopAsyncIteration
        doc = _FakeDoc(self._docs[self._index])
        self._index += 1
        return doc


class _FakeCollection:
    def __init__(self, docs: list[dict[str, Any]], filters: list[Any] | None = None):
        self._docs = docs
        self._filters = list(filters or [])

    def where(self, *, filter: Any):
        return _FakeCollection(self._docs, self._filters + [filter])

    def stream(self):
        docs = list(self._docs)
        for flt in self._filters:
            field = getattr(flt, "field_path", "")
            value = getattr(flt, "value", None)
            docs = [doc for doc in docs if doc.get(field) == value]
        return _FakeAsyncStream(docs)


class _FakeDB:
    def __init__(self, *, work_orders: list[dict[str, Any]], assets: list[dict[str, Any]]):
        self._collections = {
            "work_orders": _FakeCollection(work_orders),
            "assets": _FakeCollection(assets),
        }

    def collection(self, name: str):
        return self._collections[name]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_firestore_search_work_orders_handles_nullable_assigned_to() -> None:
    work_orders = [
        {
            "wo_id": "WO-2026-0152",
            "asset_id": "ESC-SC-003",
            "status": "open",
            "priority": "P4",
            "problem_code": "ME-003",
            "fault_code": "LUB-DRY",
            "action_code": "LUBRICATE",
            "failure_class": "MECHANICAL",
            "description": "Routine lubrication needed",
            "assigned_to": None,
        }
    ]
    assets = [
        {
            "asset_id": "ESC-SC-003",
            "name": "Stadium-Chinatown Escalator #3",
            "department": "elevating_devices",
            "location": {"station": "Stadium-Chinatown"},
        }
    ]

    eam = FirestoreEAM.__new__(FirestoreEAM)
    eam.db = _FakeDB(work_orders=work_orders, assets=assets)

    results = await FirestoreEAM.search_work_orders(
        eam,
        q="is there any work order for escalator three at stadium chinatown",
        status=WorkOrderStatus.OPEN,
    )

    assert len(results) == 1
    assert results[0].wo_id == "WO-2026-0152"
