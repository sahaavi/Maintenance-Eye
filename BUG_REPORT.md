# Bug Report & System Audit — Maintenance-Eye 🔍

**Date**: February 28, 2026
**Status**: Critical Issues Identified
**Total Issues**: 32 (8 Critical, 6 Architectural/High, 5 Feature Gaps, 4 Tech Debt, 9 Medium)

## 1. Critical Bugs (Immediate Resolution Required)

| ID | Component | Issue | Impact |
|:---|:---|:---|:---|
| **C-001** (Fixed — Removed firestore.ArrayUnion dependency; notes passed as plain list. (2026-02-28)) | `agent/tools/work_order.py:84` | `NameError`: `firestore.ArrayUnion` used without import. Also, `priority` param defaults to `"P3"` (line 25), so `if priority:` is always True — every update silently overwrites priority to P3. | Tool crashes on `update` action; priority corruption on all updates. |
| **C-002** | `agent/tools/confirm_action.py:23-29` | Global `_current_session_id` is not thread-safe/async-safe. A single module-level variable is shared across all concurrent sessions. | Multi-user sessions will overwrite each other, routing actions to wrong technicians. Fix: use `contextvars.ContextVar` or pass session_id as tool argument. |
| **C-003** | `agent/tools/*.py` | `asyncio.run_until_complete()` used inside a running event loop. | Will raise `RuntimeError: This event loop is already running`. |
| **C-004** | `api/websocket.py` | Missing logic to route `confirmation_prompt` to WebSocket. | Technician never sees "Confirm/Reject/Correct" cards in the UI. |
| **C-005** | `frontend/app.js:276-280` + `api/websocket.py:211-274` | WebSocket payload mismatch for confirm/reject/correct. Frontend `wsSend()` wraps everything in `{"type": ..., "data": {...}}`, but backend reads `message.get("action_id")` / `message.get("notes")` / `message.get("corrections")` from top level — always returns empty string. | Human-in-the-loop confirmations silently fail; approvals are not processed. |
| **C-006** (Fixed 2026-02-28) | `api/websocket.py:267,276` | ADK `LiveRequestQueue.send_realtime()` API changed from keyword args (`audio=`, `video=`) to single positional `blob` param in ADK 1.10.0. | All audio/video streaming to Gemini fails with TypeError. Inspection mode non-functional. |
| **C-007** (Fixed 2026-02-28) | `config.py:26` | Gemini Live model name `gemini-live-2.5-flash-native-audio` does not exist. Correct name is `gemini-2.5-flash-native-audio-latest`. | Live API connection fails on every inspection session. Agent cannot respond. |
| **C-008** (Fixed 2026-02-28) | `services/firestore_eam.py:252-257` | Agent tools have no fallback to `seed_data.json` when Firestore unavailable, unlike REST API routes which do. | Agent cannot find any assets, work orders, or knowledge base entries in local dev. |

## 2. Architectural Misalignments

| ID | Feature | Requirement | Current State |
|:---|:---|:---|:---|
| **A-001** | Authentication | Firebase Auth (from Context) | No auth implemented. Random IDs used. |
| **A-002** | Feedback Loop | Log corrections to EAM for AI training. | Corrections only stored in memory; `log_correction` never called. |
| **A-003** | Safety Protocol | Enforce LOTO/PPE before inspection. | No enforced sequencing in agent prompts or tools. |
| **A-004** | Persistent Storage | Photos stored in Cloud Storage (GCS). | Photos only streamed to Gemini; never persisted to GCS. |
| **A-005** | Security Baseline | Restrictive CORS and Firestore access controls for production posture. | `allow_origins=["*"]` and Firestore rules allow `read, write: if true`. Both `cloudbuild.yaml` and `terraform/main.tf` deploy these same open rules to production. Additionally, `GEMINI_API_KEY` is set as plaintext env var on Cloud Run (visible to anyone with `run.services.get`); should use Secret Manager. `deploy.sh` also writes the key to `terraform.tfvars` on disk. |

## 3. Missing Features & UX Gaps

| ID | Feature | Description | Priority |
|:---|:---|:---|:---|
| **F-001** | Location Aware | `lookup_asset` supports GPS, but frontend does not send coordinates. | High |
| **F-002** | Report Links | Agent cannot provide a direct URL to the generated PDF/HTML report. | Medium |
| **F-003** | Auto-Replication | No retry logic in WebSocket for Live API timeouts/disconnects. | Medium |
| **F-004** | Work Order Filtering | `/api/work-orders` accepts `status` but does not apply it in service query. | Medium |
| **F-005** | Open WO Accuracy | Open work order detection compares enum values to raw strings in tools. | Medium |

## 4. Technical Debt

*   **Testing**: Zero unit tests for ADK tools or EAM service abstraction.
*   **Documentation**: Tool docstrings mention `waiting for response` but don't define the schema for that response clearly for the LLM. PROJECT_CONTEXT.md and README list only 6 tools, omitting `propose_action` and `check_pending_actions` — the human-in-the-loop tools should be highlighted as a differentiator.
*   **Logging**: Insufficient logging of raw tool results for debugging multimodal failures.
*   **PWA Reliability**: Service worker exists but `app.js:808-819` unregisters all service workers and clears caches on every page load. `manifest.json` also only provides one SVG icon with `"sizes": "any"` — Chrome requires 192x192 and 512x512 PNG icons for PWA installability.

## 5. High-Severity Bugs

| ID | Component | Issue | Impact |
|:---|:---|:---|:---|
| **H-001** | `Dockerfile:39-42` | `data/` directory is not copied into Docker image. `routes.py` fallback path resolves to `/data/seed_data.json` which won't exist in the container. | All JSON fallback REST endpoints return errors in production Docker deployment. |
| **H-002** | `frontend/app.js:551-593, 371-389` | Multiple functions use `innerHTML` to insert server/agent-provided text without sanitization (`addAgentMessage`, `addUserMessage`, `addTranscript`, `addFinding`, `renderConfirmationCard`). | XSS vulnerability — AI model output containing HTML/script tags will execute in the browser. |
| **H-003** | `frontend/app.js:156-160` | `playbackCtx` (AudioContext) is created inside `ws.onopen`, which is not a user gesture. Modern browsers (Chrome, Safari) keep it suspended. | Agent voice audio playback may be completely silent. Fix: call `playbackCtx.resume()` or create context during `startInspection()` click. |
| **H-004** | `terraform/main.tf` + `scripts/deploy.sh:71` | `deploy.sh` runs `terraform output -raw service_url` but no `output "service_url"` block is defined in `main.tf`. | Deploy script crashes when Terraform is installed (`set -euo pipefail` causes exit). |
| **H-005** | `services/firestore_eam.py:91-99` | Work order ID counter increment is not atomic. Two concurrent creates read same counter, both increment to same value. | Duplicate work order IDs in concurrent usage. Fix: use `firestore.Increment(1)` or a transaction. |
| **H-006** (Fixed 2026-02-28) | `frontend/style.css:769` | CSS `#dashboard-screen` has `display:flex` which overrides `.screen { display:none }` due to ID selector specificity. | Splash screen hidden behind dashboard. Start Inspection and back button both appear broken. |

## 6. Medium-Severity Bugs

| ID | Component | Issue | Impact |
|:---|:---|:---|:---|
| **M-001** | `api/routes.py:75-77, 101-103, 135-137` | If Firestore is connected but a query returns zero results, code falls through to stale JSON fallback instead of returning empty list. | REST API returns stale seed data when live database has no matching records. |
| **M-002** | `api/routes.py:218` | Mutable default argument `corrections: dict = {}` on `correct_action` endpoint. | Shared mutable default across invocations — latent mutation bug. Fix: use `None` default. |
| **M-003** | `api/websocket.py:350` | `event.interrupted` accessed directly without `hasattr()` guard (unlike lines 328, 335 which use guards). | `AttributeError` if event type lacks `interrupted` attribute. |
| **M-004** | `api/websocket.py:370-374` | `asyncio.gather` with `return_exceptions=True` — return value never inspected. When one task fails, the other keeps running. No cancellation logic when upstream finishes. | Zombie tasks after client disconnect; downstream continues until Live API timeout. |
| **M-005** | `api/websocket.py:105` | Session ID uses `id(websocket)` (memory address), which can be reused after GC. | Possible session ID collision if WebSocket objects are rapidly created/destroyed. |
| **M-006** | `frontend/app.js:193-196` | `clearPlaybackQueue()` empties queue but does not stop currently playing `BufferSource`. No reference kept to active source to call `.stop()`. | On barge-in/interrupt, current audio chunk continues playing until its buffer finishes. |
| **M-007** | `frontend/app.js:551-577` | `addAgentMessage`, `addUserMessage`, `addTranscript` append DOM elements with no limit. | Unbounded DOM growth during long sessions — degraded performance and memory consumption. |
| **M-008** | `frontend/app.js:470-496` | `endInspection` sends `end_session` then immediately closes WebSocket. No delivery guarantee. | `end_session` message may not be delivered if close handshake completes first. |
| **M-009** (Fixed 2026-02-28) | `config.py:30-33` | Config sets both `GOOGLE_API_KEY` and `GEMINI_API_KEY` env vars, causing genai client to warn on every API call. | Noisy terminal warnings polluting logs. |

## 7. Action Plan for Agents

### P1 — Blocks demo functionality
1.  [x] **Fix C-001**: Removed `firestore.ArrayUnion` import; notes passed as plain list. (2026-02-28)
2.  [ ] **Fix C-003**: Refactor all tools to `async def` and remove `asyncio.run_until_complete()`.
3.  [ ] **Fix C-002**: Replace global session state with `contextvars` or pass `session_id` as a tool argument (preferred for ADK).
4.  [ ] **Fix C-004**: Update `websocket.py` to intercept `confirmation_prompt` in tool outputs and emit `type: confirmation_request`.
5.  [ ] **Fix C-005**: Align frontend/backend WebSocket confirmation payload contract (`action_id`, `notes`, `corrections`).
6.  [x] **Fix C-006**: Changed `send_realtime()` from keyword args to positional blob param for ADK 1.10.0. (2026-02-28)
7.  [x] **Fix C-007**: Corrected model name to `gemini-2.5-flash-native-audio-latest`. (2026-02-28)
8.  [x] **Fix C-008**: Created `JsonEAM` fallback and updated `get_eam_service()` singleton. (2026-02-28)
9.  [x] **Fix H-006**: Changed `#dashboard-screen` to `#dashboard-screen.active` in CSS. (2026-02-28)
10. [ ] **Fix H-003**: Resume or create `AudioContext` during user gesture so agent voice plays.
11. [ ] **Fix H-002**: Replace `innerHTML` with `textContent` for user/agent messages to prevent XSS.

### P2 — Deployment & infrastructure
7.  [ ] **Fix H-001**: Add `COPY data/ /app/data/` to Dockerfile and fix path resolution in `routes.py`.
8.  [ ] **Fix H-004**: Add `output "service_url"` block to `terraform/main.tf`.
9.  [ ] **Fix H-005**: Use atomic Firestore increment for work order counter.
10. [ ] **Fix F-004/F-005**: Apply status filter in `/api/work-orders` and normalize enum comparisons for open work order logic.
11. [ ] **Fix M-001**: Return empty list when Firestore returns zero results instead of falling through to stale JSON.

### P3 — Architectural & feature gaps
12. [ ] **Implement A-004**: Add GCS upload logic when `video` (photo) frames are received or when a report is generated.
13. [ ] **Implement A-001/A-005**: Set up Firebase Auth, tighten production CORS + Firestore rules, move API key to Secret Manager.
14. [ ] **Fix PWA debt**: Stop unconditional service-worker unregister/cache purge in `frontend/app.js`. Add required PWA icon sizes.
15. [ ] **Fix M-003/M-004**: Add `hasattr` guard for `event.interrupted`; add task cancellation logic in WebSocket gather.
16. [ ] **Fix M-006/M-007/M-008**: Cap message DOM growth, stop active audio on interrupt, ensure `end_session` delivery before close.

### Missing files
17. [ ] Update PROJECT_CONTEXT.md and README to list all 8 tools (currently only 6).