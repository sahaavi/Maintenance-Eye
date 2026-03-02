from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

from tests.config.settings import SETTINGS


@pytest.fixture(scope="module")
def static_server() -> str:
    root = Path(__file__).resolve().parents[2]
    frontend = root / "frontend"

    process = subprocess.Popen(
        ["python3", "-m", "http.server", "4173", "--directory", str(frontend)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(1.0)
    yield "http://127.0.0.1:4173"

    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def page() -> Page:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


@pytest.mark.e2e
@pytest.mark.slow
def test_home_to_dashboard_navigation(page: Page, static_server: str) -> None:
    mock_assets = [{
        "asset_id": "AST-UNIT-001",
        "name": "Signal Cabinet",
        "department": "signal_telecom",
        "type": "signal",
        "location": {"station": "Main Station", "station_code": "MS", "zone": "Z1"},
        "status": "operational",
    }]
    mock_work_orders = [{
        "wo_id": "WO-2026-0001",
        "priority": "P2",
        "description": "Check bracket",
        "asset_id": "AST-UNIT-001",
        "status": "open",
        "problem_code": "ME-003",
        "created_at": "2026-03-02T00:00:00",
    }]

    def fulfill_api(route):
        path = route.request.url
        if "/api/assets" in path:
            route.fulfill(status=200, body=json.dumps(mock_assets), content_type="application/json")
            return
        if "/api/work-orders" in path:
            route.fulfill(status=200, body=json.dumps(mock_work_orders), content_type="application/json")
            return
        if "/api/locations" in path:
            route.fulfill(status=200, body=json.dumps([{"station": "Main Station", "station_code": "MS", "zone": "Z1", "asset_count": 1}]), content_type="application/json")
            return
        if "/api/knowledge" in path:
            route.fulfill(status=200, body=json.dumps([]), content_type="application/json")
            return
        if "/api/eam-codes" in path:
            route.fulfill(status=200, body=json.dumps([]), content_type="application/json")
            return
        route.fulfill(status=200, body="[]", content_type="application/json")

    page.route("**/api/**", fulfill_api)

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_role("button", name="Browse Data").click()

    expect_title = page.locator("#dash-topbar .dashboard-title")
    expect_title.wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)
    assert expect_title.inner_text() == "Data Explorer"

    page.get_by_role("button", name="Assets").click()
    page.locator("#page-assets").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)


@pytest.mark.e2e
@pytest.mark.slow
def test_chat_panel_toggle(page: Page, static_server: str) -> None:
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)

    page.get_by_role("button", name="Chat with Max").click()
    chat_panel = page.locator("#chat-panel")
    chat_panel.wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)

    page.locator("#chat-panel .btn-icon").first.click()
    assert page.locator("#chat-panel").is_hidden()
