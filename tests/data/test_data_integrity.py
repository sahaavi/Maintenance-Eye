from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT / "data" / "seed_data.json"
DRIFT_BASELINE_PATH = ROOT / "tests" / "data" / "drift_baseline.json"


@pytest.mark.data
def test_seed_data_referential_integrity() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    assets = payload["assets"]
    work_orders = payload["work_orders"]
    inspections = payload["inspections"]

    asset_ids = {asset["asset_id"] for asset in assets}
    assert len(asset_ids) == len(assets)

    for wo in work_orders:
        assert wo["asset_id"] in asset_ids

    for inspection in inspections:
        assert inspection["asset_id"] in asset_ids


@pytest.mark.data
def test_seed_data_required_domains_and_values() -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    allowed_priorities = {"P1", "P2", "P3", "P4", "P5"}
    allowed_status = {"open", "in_progress", "on_hold", "completed", "cancelled"}

    for wo in payload["work_orders"]:
        assert wo["priority"] in allowed_priorities
        assert wo["status"] in allowed_status


@pytest.mark.data
@pytest.mark.ai
def test_data_drift_against_baseline_distribution() -> None:
    baseline = json.loads(DRIFT_BASELINE_PATH.read_text(encoding="utf-8"))
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    asset_count = len(payload["assets"])
    wo_count = len(payload["work_orders"])
    assert abs(asset_count - baseline["asset_count"]) <= 10
    assert abs(wo_count - baseline["work_order_count"]) <= 20

    department_distribution = Counter(asset["department"] for asset in payload["assets"])
    priority_distribution = Counter(wo["priority"] for wo in payload["work_orders"])

    for key, baseline_value in baseline["asset_department_distribution"].items():
        assert abs(department_distribution.get(key, 0) - baseline_value) <= 5

    for key, baseline_value in baseline["work_order_priority_distribution"].items():
        assert abs(priority_distribution.get(key, 0) - baseline_value) <= 8
