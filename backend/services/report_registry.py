"""
In-memory report registry for locally generated inspection reports.

Generated reports need stable URLs for the demo UI even when object storage is
disabled. This registry intentionally stays process-local; cloud storage remains
the durable audit path when configured.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_REPORTS: dict[str, dict[str, Any]] = {}


def store_report(report: dict[str, Any]) -> str:
    report_id = str(report.get("report_id", "")).strip()
    if not report_id:
        raise ValueError("Report is missing report_id")
    _REPORTS[report_id] = deepcopy(report)
    return report_id


def get_report(report_id: str) -> dict[str, Any] | None:
    report = _REPORTS.get(report_id)
    return deepcopy(report) if report is not None else None
