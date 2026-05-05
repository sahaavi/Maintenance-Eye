from __future__ import annotations

import pytest
from services.report_renderer import render_report_html  # type: ignore[import-not-found]


@pytest.mark.unit
def test_report_renderer_uses_nested_asset_schema_fields() -> None:
    html = render_report_html(
        {
            "report_id": "RPT-UNIT",
            "generated_at": "2026-05-05T12:00:00",
            "asset": {
                "asset_id": "ESC-SC-003",
                "name": "Stadium-Chinatown Escalator #3",
                "type": "escalator",
                "department": "elevating_devices",
                "location": {"station": "Stadium-Chinatown", "zone": "Concourse"},
            },
            "inspector": "Field Technician",
            "overall_condition": "requires_attention",
            "findings_summary": "Step chain lubrication looks dry.",
            "open_work_orders": [],
            "next_inspection_recommendation": "Follow up in 30 days",
        }
    )

    assert "escalator" in html
    assert "Stadium-Chinatown" in html
    assert "elevating devices" in html
    assert "{&#39;station&#39;" not in html
