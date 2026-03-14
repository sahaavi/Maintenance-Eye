from __future__ import annotations

import time

import pytest
from services.json_eam import JsonEAM  # type: ignore[import-not-found]


@pytest.mark.performance
@pytest.mark.asyncio
async def test_search_work_orders_latency_under_threshold() -> None:
    eam = JsonEAM()

    start = time.perf_counter()
    for _ in range(100):
        await eam.search_work_orders(q="wear", priority="P3")
    duration = time.perf_counter() - start

    assert duration < 2.0


@pytest.mark.performance
@pytest.mark.asyncio
async def test_search_assets_latency_under_threshold() -> None:
    eam = JsonEAM()

    start = time.perf_counter()
    for _ in range(100):
        await eam.search_assets(query="station")
    duration = time.perf_counter() - start

    assert duration < 2.0
