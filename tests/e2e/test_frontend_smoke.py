from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

from tests.config.settings import SETTINGS

MOCK_ASSETS = [
    {
        "asset_id": "AST-UNIT-001",
        "name": "Signal Cabinet",
        "department": "signal_telecom",
        "type": "signal",
        "location": {"station": "Main Station", "station_code": "MS", "zone": "Z1"},
        "status": "operational",
        "manufacturer": "Wayside Systems",
    },
    {
        "asset_id": "AHU-07",
        "name": "Rooftop Unit 7",
        "department": "facilities",
        "type": "hvac",
        "location": {"station": "Building A", "station_code": "BA", "zone": "North"},
        "status": "degraded",
        "manufacturer": "MetroAir",
    },
]

MOCK_WORK_ORDERS = [
    {
        "wo_id": "WO-245871",
        "priority": "P2",
        "description": "Bearing inspection",
        "asset_id": "AHU-07",
        "status": "in_progress",
        "problem_code": "ME-003",
        "created_at": "2026-05-02T16:00:00",
    },
    {
        "wo_id": "WO-245858",
        "priority": "P1",
        "description": "Oil leakage detected",
        "asset_id": "AST-UNIT-001",
        "status": "open",
        "problem_code": "FL-001",
        "created_at": "2026-05-02T15:00:00",
    },
]


def route_demo_api(page: Page) -> None:
    def fulfill_api(route):
        path = route.request.url
        if "/api/assets" in path:
            route.fulfill(status=200, body=json.dumps(MOCK_ASSETS), content_type="application/json")
            return
        if "/api/work-orders" in path:
            route.fulfill(
                status=200, body=json.dumps(MOCK_WORK_ORDERS), content_type="application/json"
            )
            return
        if "/api/locations" in path:
            route.fulfill(
                status=200,
                body=json.dumps(
                    [
                        {
                            "station": "Main Station",
                            "station_code": "MS",
                            "zone": "Z1",
                            "asset_count": 1,
                        },
                        {
                            "station": "Building A",
                            "station_code": "BA",
                            "zone": "North",
                            "asset_count": 1,
                        },
                    ]
                ),
                content_type="application/json",
            )
            return
        if "/api/knowledge" in path or "/api/eam-codes" in path:
            route.fulfill(status=200, body=json.dumps([]), content_type="application/json")
            return
        route.fulfill(status=200, body="[]", content_type="application/json")

    page.route("**/api/**", fulfill_api)


def install_media_mocks(page: Page, include_websocket: bool = False) -> None:
    websocket_script = """
        window.__wsMessages = [];
        class FakeWebSocket {
          constructor(url) {
            this.url = url;
            this.readyState = FakeWebSocket.CONNECTING;
            setTimeout(() => {
              this.readyState = FakeWebSocket.OPEN;
              if (this.onopen) this.onopen();
            }, 0);
          }
          send(payload) { window.__wsMessages.push(JSON.parse(payload)); }
          close() {
            this.readyState = FakeWebSocket.CLOSED;
            if (this.onclose) this.onclose({ code: 1000 });
          }
        }
        FakeWebSocket.CONNECTING = 0;
        FakeWebSocket.OPEN = 1;
        FakeWebSocket.CLOSING = 2;
        FakeWebSocket.CLOSED = 3;
        window.WebSocket = FakeWebSocket;
    """
    page.add_init_script(
        f"""
        Object.defineProperty(navigator, 'mediaDevices', {{
          configurable: true,
          value: {{
          getUserMedia: async () => {{
            const stream = new MediaStream();
            stream.getTracks = () => [{{ stop() {{}} }}];
            stream.getAudioTracks = () => [{{ stop() {{}}, enabled: true }}];
            stream.getVideoTracks = () => [{{ stop() {{}}, enabled: true }}];
            return stream;
          }}
          }}
        }});
        window.AudioContext = window.webkitAudioContext = function () {{
          return {{
            state: 'running',
            close() {{}},
            resume() {{}},
            createMediaStreamSource() {{ return {{ connect() {{}} }}; }},
            createScriptProcessor() {{
              return {{ connect() {{}}, disconnect() {{}}, onaudioprocess: null }};
            }},
            createBuffer() {{ return {{ getChannelData() {{ return new Float32Array(1); }} }}; }},
            createBufferSource() {{
              return {{ connect() {{}}, start() {{}}, stop() {{}}, onended: null }};
            }}
          }};
        }};
        Object.defineProperty(HTMLMediaElement.prototype, 'videoWidth', {{
          configurable: true,
          get() {{ return this.id === 'camera-feed' ? 1280 : 0; }}
        }});
        Object.defineProperty(HTMLMediaElement.prototype, 'videoHeight', {{
          configurable: true,
          get() {{ return this.id === 'camera-feed' ? 720 : 0; }}
        }});
        HTMLMediaElement.prototype.play = async function () {{
          this.dispatchEvent(new Event('loadedmetadata'));
        }};
        {websocket_script if include_websocket else ""}
        """
    )


def install_speech_recognition_mock(page: Page) -> None:
    page.add_init_script(
        """
        window.__recognitions = [];
        window.__recognitionStartCalls = 0;
        class FakeSpeechRecognition {
          constructor() {
            this.continuous = false;
            this.interimResults = false;
            this.lang = 'en-US';
            this.started = false;
            window.__recognitions.push(this);
          }
          start() {
            window.__recognitionStartCalls += 1;
            if (this.started) throw new Error('recognition already started');
            this.started = true;
            if (this.onstart) this.onstart();
          }
          stop() {
            const wasStarted = this.started;
            this.started = false;
            if (wasStarted && this.onend) this.onend();
          }
          emitFinal(text) {
            const result = [{ transcript: text }];
            result.isFinal = true;
            if (this.onresult) this.onresult({ resultIndex: 0, results: [result] });
            this.started = false;
            if (this.onend) this.onend();
          }
        }
        window.SpeechRecognition = FakeSpeechRecognition;
        window.webkitSpeechRecognition = FakeSpeechRecognition;
        window.__emitVoiceFinal = (text) => {
          const recognition = window.__recognitions[window.__recognitions.length - 1];
          if (!recognition) throw new Error('No recognition instance');
          recognition.emitFinal(text);
        };
        """
    )


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
        context = browser.new_context(service_workers="block")
        page = context.new_page()
        yield page
        context.close()
        browser.close()


@pytest.mark.e2e
@pytest.mark.slow
def test_home_to_dashboard_navigation(page: Page, static_server: str) -> None:
    route_demo_api(page)

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_role("button", name="Browse enterprise data explorer").click()

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


@pytest.mark.e2e
@pytest.mark.slow
def test_chat_voice_sends_multiple_final_transcripts(page: Page, static_server: str) -> None:
    route_demo_api(page)
    install_media_mocks(page, include_websocket=True)
    install_speech_recognition_mock(page)

    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("open-chat").click()
    page.locator("#chat-panel").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)
    page.locator("#btn-chat-voice").click()

    page.evaluate("window.__emitVoiceFinal('first envelope sentence')")
    page.wait_for_timeout(350)
    page.evaluate("window.__emitVoiceFinal('second question')")

    page.wait_for_function(
        """
        () => window.__wsMessages.filter((msg) => msg.type === 'text').length === 2
        """,
        timeout=SETTINGS.e2e_timeout_ms,
    )
    sent_texts = page.evaluate(
        "window.__wsMessages.filter((msg) => msg.type === 'text').map((msg) => msg.data)"
    )
    assert sent_texts == ["first envelope sentence", "second question"]
    assert page.evaluate("window.__recognitionStartCalls") >= 2


@pytest.mark.e2e
@pytest.mark.slow
def test_chat_voice_queues_transcript_until_socket_opens(page: Page, static_server: str) -> None:
    route_demo_api(page)
    install_speech_recognition_mock(page)
    page.add_init_script(
        """
        window.__wsMessages = [];
        window.__wsInstances = [];
        class ControlledWebSocket {
          constructor(url) {
            this.url = url;
            this.readyState = ControlledWebSocket.CONNECTING;
            window.__wsInstances.push(this);
          }
          open() {
            this.readyState = ControlledWebSocket.OPEN;
            if (this.onopen) this.onopen();
          }
          send(payload) { window.__wsMessages.push(JSON.parse(payload)); }
          close() {
            this.readyState = ControlledWebSocket.CLOSED;
            if (this.onclose) this.onclose({ code: 1000 });
          }
        }
        ControlledWebSocket.CONNECTING = 0;
        ControlledWebSocket.OPEN = 1;
        ControlledWebSocket.CLOSING = 2;
        ControlledWebSocket.CLOSED = 3;
        window.WebSocket = ControlledWebSocket;
        """
    )

    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("open-chat").click()
    page.locator("#chat-panel").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)
    page.locator("#btn-chat-voice").click()
    page.evaluate("window.__emitVoiceFinal('second question')")

    assert page.evaluate("window.__wsMessages.length") == 0
    assert page.evaluate("window.chatState.pendingSends.length") == 1
    assert "Connection is reconnecting" in page.locator("#chat-messages").inner_text()

    page.evaluate("window.__wsInstances[0].open()")
    page.wait_for_function(
        "() => window.__wsMessages.some((msg) => msg.type === 'text')",
        timeout=SETTINGS.e2e_timeout_ms,
    )
    sent_texts = page.evaluate(
        "window.__wsMessages.filter((msg) => msg.type === 'text').map((msg) => msg.data)"
    )
    assert sent_texts == ["second question"]
    assert page.evaluate("window.chatState.pendingSends.length") == 0
    assert page.locator("#chat-messages").get_by_text("second question").is_visible()


@pytest.mark.e2e
@pytest.mark.slow
def test_chat_panel_controls_fit_common_viewports(page: Page, static_server: str) -> None:
    route_demo_api(page)
    install_media_mocks(page, include_websocket=True)

    viewports = [
        {"width": 320, "height": 568},
        {"width": 375, "height": 667},
        {"width": 390, "height": 844},
        {"width": 414, "height": 896},
        {"width": 768, "height": 1024},
        {"width": 1280, "height": 800},
    ]
    visible_selectors = [
        "#chat-panel",
        ".chat-input-bar",
        "#btn-chat-attach",
        "#chat-input",
        "#btn-chat-voice",
        "#btn-chat-send",
    ]

    for viewport_size in viewports:
        page.set_viewport_size(viewport_size)
        page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)
        page.get_by_test_id("open-chat").click()
        page.locator("#chat-panel").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)

        metrics = page.evaluate(
            """
            () => ({
              width: window.visualViewport?.width ?? window.innerWidth,
              height: window.visualViewport?.height ?? window.innerHeight,
              clientWidth: document.documentElement.clientWidth,
              scrollWidth: document.documentElement.scrollWidth,
              bodyScrollWidth: document.body.scrollWidth
            })
            """
        )

        for selector in visible_selectors:
            box = page.locator(selector).bounding_box()
            assert box is not None, f"{selector} missing at {viewport_size}"
            assert box["width"] > 0, f"{selector} has no width at {viewport_size}"
            assert box["height"] > 0, f"{selector} has no height at {viewport_size}"
            assert box["x"] >= -1, f"{selector} overflows left at {viewport_size}: {box}"
            assert box["x"] + box["width"] <= metrics["width"] + 1, (
                f"{selector} overflows right at {viewport_size}: {box}"
            )
            assert box["y"] >= -1, f"{selector} overflows top at {viewport_size}: {box}"
            assert box["y"] + box["height"] <= metrics["height"] + 1, (
                f"{selector} overflows bottom at {viewport_size}: {box}"
            )

        assert metrics["scrollWidth"] <= metrics["clientWidth"] + 1
        assert metrics["bodyScrollWidth"] <= metrics["clientWidth"] + 1


@pytest.mark.e2e
@pytest.mark.slow
def test_dashboard_renders_command_center_metrics_when_data_loads(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("open-dashboard").click()

    page.get_by_test_id("dashboard-summary").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    assert page.get_by_test_id("summary-open-work-orders").inner_text().strip() == "2"
    assert page.get_by_test_id("summary-high-priority").inner_text().strip() == "1"
    assert page.locator("#wo-tbody").get_by_text("WO-245871").is_visible()
    assert page.locator("#page-work-orders .dash-error").is_hidden()


@pytest.mark.e2e
@pytest.mark.slow
def test_asset_selection_updates_inspection_asset_context(page: Page, static_server: str) -> None:
    route_demo_api(page)
    install_media_mocks(page)

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("start-inspection").click()
    page.get_by_test_id("asset-picker").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("asset-option-AHU-07").click()
    page.get_by_test_id("confirm-asset-selection").click()

    page.locator("#inspection-screen.active").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    assert "AHU-07" in page.locator("#session-asset").inner_text()


@pytest.mark.e2e
@pytest.mark.slow
def test_inspection_start_sends_top_level_asset_id(page: Page, static_server: str) -> None:
    route_demo_api(page)
    install_media_mocks(page, include_websocket=True)

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("start-inspection").click()
    page.get_by_test_id("asset-option-AHU-07").click()
    page.get_by_test_id("confirm-asset-selection").click()

    page.wait_for_function(
        "() => window.__wsMessages.some((msg) => msg.type === 'start_session')",
        timeout=SETTINGS.e2e_timeout_ms,
    )
    start_messages = page.evaluate(
        "window.__wsMessages.filter((msg) => msg.type === 'start_session')"
    )
    assert start_messages[0] == {"type": "start_session", "asset_id": "AHU-07"}
    assert "data" not in start_messages[0]


@pytest.mark.e2e
@pytest.mark.slow
def test_start_inspection_ignores_duplicate_start_while_media_pending(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)
    page.add_init_script(
        """
        window.__mediaCalls = 0;
        window.__wsMessages = [];
        window.__wsUrls = [];
        window.__resolveMedia = null;
        Object.defineProperty(navigator, 'mediaDevices', {
          configurable: true,
          value: {
            getUserMedia: async () => {
              window.__mediaCalls += 1;
              return new Promise((resolve) => {
                window.__resolveMedia = () => {
                  const stream = new MediaStream();
                  stream.getTracks = () => [{ stop() {} }];
                  stream.getAudioTracks = () => [{ stop() {}, enabled: true }];
                  stream.getVideoTracks = () => [{ stop() {}, enabled: true }];
                  resolve(stream);
                };
              });
            }
          }
        });
        window.AudioContext = window.webkitAudioContext = function () {
          return {
            state: 'running',
            close() {},
            resume() {},
            createMediaStreamSource() { return { connect() {} }; },
            createScriptProcessor() {
              return { connect() {}, disconnect() {}, onaudioprocess: null };
            },
            createBuffer() { return { getChannelData() { return new Float32Array(1); } }; },
            createBufferSource() {
              return { connect() {}, start() {}, stop() {}, onended: null };
            }
          };
        };
        Object.defineProperty(HTMLMediaElement.prototype, 'videoWidth', {
          configurable: true,
          get() { return this.id === 'camera-feed' ? 1280 : 0; }
        });
        Object.defineProperty(HTMLMediaElement.prototype, 'videoHeight', {
          configurable: true,
          get() { return this.id === 'camera-feed' ? 720 : 0; }
        });
        HTMLMediaElement.prototype.play = async function () {
          this.dispatchEvent(new Event('loadedmetadata'));
        };
        class FakeWebSocket {
          constructor(url) {
            this.url = url;
            this.readyState = FakeWebSocket.CONNECTING;
            window.__wsUrls.push(url);
            setTimeout(() => {
              this.readyState = FakeWebSocket.OPEN;
              if (this.onopen) this.onopen();
            }, 0);
          }
          send(payload) { window.__wsMessages.push(JSON.parse(payload)); }
          close() {
            this.readyState = FakeWebSocket.CLOSED;
            if (this.onclose) this.onclose({ code: 1000 });
          }
        }
        FakeWebSocket.CONNECTING = 0;
        FakeWebSocket.OPEN = 1;
        FakeWebSocket.CLOSING = 2;
        FakeWebSocket.CLOSED = 3;
        window.WebSocket = FakeWebSocket;
        """
    )

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("start-inspection").click()
    page.get_by_test_id("asset-option-AHU-07").click()
    page.get_by_test_id("confirm-asset-selection").click()
    page.get_by_test_id("start-inspection").click()
    page.evaluate("window.__resolveMedia()")

    page.wait_for_function(
        "() => window.__wsMessages.some((msg) => msg.type === 'start_session')",
        timeout=SETTINGS.e2e_timeout_ms,
    )
    assert page.evaluate("window.__mediaCalls") == 1
    assert page.evaluate("window.__wsUrls.length") == 1
    start_messages = page.evaluate(
        "window.__wsMessages.filter((msg) => msg.type === 'start_session')"
    )
    assert len(start_messages) == 1


@pytest.mark.e2e
@pytest.mark.slow
def test_start_inspection_shows_permission_failure_without_leaving_home(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'mediaDevices', {
          configurable: true,
          value: {
            getUserMedia: async () => { throw new Error('permission denied'); }
          }
        });
        """
    )

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("start-inspection").click()
    page.get_by_test_id("asset-option-AHU-07").click()
    page.get_by_test_id("confirm-asset-selection").click()

    status = page.locator("#splash-status")
    status.wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)
    assert "Camera/mic access failed" in status.inner_text()
    assert page.locator("#splash-screen").evaluate("el => el.classList.contains('active')")
    assert not page.locator("#inspection-screen").evaluate("el => el.classList.contains('active')")


@pytest.mark.e2e
@pytest.mark.slow
def test_confirmation_card_correct_opens_inline_editor_and_sends_corrections(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)

    page.evaluate(
        """
        window.__sentMessages = [];
        window.wsSend = (type, data) => window.__sentMessages.push({ type, data });
        document.getElementById('splash-screen').classList.remove('active');
        document.getElementById('inspection-screen').classList.add('active');
        window.renderConfirmationCard({
          action_id: 'ACT-123',
          confirmation_prompt: {
            action_type: 'create_work_order',
            description: 'Create work order for bearing inspection',
            asset_id: 'AHU-07',
            priority: 'P3',
            confidence: '78%',
            codes: 'Problem: ME-003 | Fault: WEAR-SUR | Action: REPAIR'
          }
        });
        """
    )

    page.locator("#confirm-ACT-123").get_by_role("button", name="Correct").click()
    page.get_by_test_id("confirmation-editor").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    page.get_by_test_id("editor-priority").fill("P2")
    page.get_by_test_id("editor-problem-code").fill("ME-005")
    page.get_by_test_id("editor-notes").fill("Technician corrected priority.")
    page.get_by_test_id("save-confirmation-correction").click()

    sent = page.evaluate("window.__sentMessages")
    assert sent[-1]["type"] == "correct"
    assert sent[-1]["data"]["action_id"] == "ACT-123"
    assert sent[-1]["data"]["corrections"]["priority"] == "P2"
    assert sent[-1]["data"]["corrections"]["problem_code"] == "ME-005"


@pytest.mark.e2e
@pytest.mark.slow
def test_confirmation_card_reject_opens_inline_editor_and_sends_notes(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)

    page.evaluate(
        """
        window.__sentMessages = [];
        window.wsSend = (type, data) => window.__sentMessages.push({ type, data });
        document.getElementById('splash-screen').classList.remove('active');
        document.getElementById('inspection-screen').classList.add('active');
        window.renderConfirmationCard({
          action_id: 'ACT-REJECT',
          confirmation_prompt: {
            action_type: 'create_work_order',
            description: 'Duplicate work order',
            asset_id: 'AHU-07',
            priority: 'P3'
          }
        });
        """
    )

    page.locator("#confirm-ACT-REJECT").get_by_role("button", name="Reject").click()
    page.get_by_test_id("confirmation-editor").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    page.get_by_test_id("editor-notes").fill("Technician rejected duplicate work order.")
    page.get_by_test_id("save-confirmation-correction").click()

    sent = page.evaluate("window.__sentMessages")
    assert sent[-1]["type"] == "reject"
    assert sent[-1]["data"] == {
        "action_id": "ACT-REJECT",
        "notes": "Technician rejected duplicate work order.",
    }


@pytest.mark.e2e
@pytest.mark.slow
def test_chat_confirmation_card_editor_sends_structured_corrections(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)

    page.evaluate(
        """
        window.__chatSentMessages = [];
        window.chatWsSend = (type, data) => window.__chatSentMessages.push({ type, data });
        window.renderChatConfirmationCard({
          action_id: 'CHAT-ACT-123',
          confirmation_prompt: {
            action_type: 'create_work_order',
            description: 'Create chat-requested work order',
            asset_id: 'AHU-07',
            priority: 'P3'
          }
        });
        """
    )

    page.locator("#chat-confirm-CHAT-ACT-123").get_by_role("button", name="Correct").click()
    page.get_by_test_id("confirmation-editor").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    page.get_by_test_id("editor-priority").fill("P2")
    page.get_by_test_id("editor-notes").fill("Corrected from chat review.")
    page.get_by_test_id("save-confirmation-correction").click()

    sent = page.evaluate("window.__chatSentMessages")
    assert sent[-1]["type"] == "correct"
    assert sent[-1]["data"]["action_id"] == "CHAT-ACT-123"
    assert sent[-1]["data"]["corrections"]["priority"] == "P2"


@pytest.mark.e2e
@pytest.mark.slow
def test_reconnect_retry_status_is_keyboard_accessible(page: Page, static_server: str) -> None:
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)
    page.evaluate(
        """
        window.__retryCount = 0;
        window.connectWebSocket = () => { window.__retryCount += 1; };
        window.updateConnectionStatus('failed');
        """
    )

    status = page.locator("#connection-status")
    assert status.get_attribute("role") == "button"
    assert status.get_attribute("tabindex") == "0"
    status.focus()
    page.keyboard.press("Enter")
    assert page.evaluate("window.__retryCount") == 1


@pytest.mark.e2e
@pytest.mark.slow
def test_dashboard_asset_filters_preserve_visible_data_state(
    page: Page, static_server: str
) -> None:
    captured_urls: list[str] = []

    def fulfill_api(route):
        url = route.request.url
        captured_urls.append(url)
        if "/api/assets" in url:
            route.fulfill(
                status=200, body=json.dumps([MOCK_ASSETS[1]]), content_type="application/json"
            )
            return
        if "/api/work-orders" in url:
            route.fulfill(
                status=200, body=json.dumps(MOCK_WORK_ORDERS), content_type="application/json"
            )
            return
        if "/api/locations" in url:
            route.fulfill(
                status=200,
                body=json.dumps([{"station": "Building A", "station_code": "BA", "zone": "North"}]),
                content_type="application/json",
            )
            return
        route.fulfill(status=200, body="[]", content_type="application/json")

    page.route("**/api/**", fulfill_api)
    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("open-dashboard").click()
    page.get_by_role("button", name="Assets").click()
    page.locator("#page-assets.active").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)

    page.locator("#asset-filter-department").select_option("facilities")
    page.locator("#asset-filter-type").select_option("hvac")
    page.locator("#asset-filter-station").select_option("Building A")

    page.locator("#asset-grid").get_by_text("AHU-07").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    assert not page.locator("#page-assets .dash-error").is_visible()
    assert any("department=facilities" in url for url in captured_urls)
    assert any("asset_type=hvac" in url for url in captured_urls)
    assert any("station=Building" in url or "station=Building+A" in url for url in captured_urls)


@pytest.mark.e2e
@pytest.mark.slow
def test_asset_picker_filters_remain_populated_after_dashboard_summary(
    page: Page, static_server: str
) -> None:
    route_demo_api(page)

    page.goto(static_server, wait_until="networkidle", timeout=SETTINGS.e2e_timeout_ms)
    page.get_by_test_id("open-dashboard").click()
    page.get_by_test_id("dashboard-summary").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    page.locator("#btn-back").click()
    page.get_by_test_id("choose-asset").click()
    page.get_by_test_id("asset-picker").wait_for(state="visible", timeout=SETTINGS.e2e_timeout_ms)

    departments = page.locator("#asset-picker-department option").all_inner_texts()
    locations = page.locator("#asset-picker-location option").all_inner_texts()
    assert "Facilities" in departments
    assert "Building A" in locations


@pytest.mark.e2e
@pytest.mark.slow
def test_confirmation_editor_blocks_noop_correction_submit(page: Page, static_server: str) -> None:
    route_demo_api(page)
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)

    page.evaluate(
        """
        window.__sentMessages = [];
        window.wsSend = (type, data) => window.__sentMessages.push({ type, data });
        document.getElementById('splash-screen').classList.remove('active');
        document.getElementById('inspection-screen').classList.add('active');
        window.renderConfirmationCard({
          action_id: 'ACT-NOOP',
          confirmation_prompt: {
            action_type: 'create_work_order',
            description: 'Create work order for bearing inspection',
            asset_id: 'AHU-07',
            priority: 'P3'
          }
        });
        """
    )

    page.locator("#confirm-ACT-NOOP").get_by_role("button", name="Correct").click()
    page.get_by_test_id("confirmation-editor").wait_for(
        state="visible", timeout=SETTINGS.e2e_timeout_ms
    )
    page.get_by_test_id("save-confirmation-correction").click()

    assert page.evaluate("window.__sentMessages") == []
    assert page.get_by_test_id("confirmation-editor").is_visible()
    assert "Change at least one field" in page.locator("#confirmation-editor").inner_text()


@pytest.mark.e2e
@pytest.mark.slow
def test_service_worker_fetch_handler_bypasses_api_cache(page: Page, static_server: str) -> None:
    page.goto(static_server, wait_until="domcontentloaded", timeout=SETTINGS.e2e_timeout_ms)

    bypasses_api = page.evaluate(
        """
        async () => {
      const script = await fetch('/sw.js').then((response) => response.text());
      const apiBypass = script.indexOf("url.pathname.startsWith('/api/')");
      const fetchCacheWrite = script.indexOf("cache.put(event.request");
      return apiBypass > -1
        && script.includes("event.respondWith(fetch(event.request));")
        && fetchCacheWrite > -1
        && apiBypass < fetchCacheWrite;
        }
        """
    )
    assert bypasses_api
