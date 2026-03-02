# Bug Report & System Audit — Maintenance-Eye 🔍

**Date**: March 1, 2026
**Status**: Critical Issues Resolved — Final Verification Pending
**Total Issues**: 7 (1 Critical, 3 Architectural/High, 4 Feature Gaps, 2 Tech Debt, 8 Medium)

## 1. Critical Bugs (Remaining)

| ID | Component | Issue | Impact | Status |
|:---|:---|:---|:---|:---|
| **C-002** | `agent/tools/confirm_action.py` | While `ContextVar` is used, the ADK runner might not propagate context to tool execution in all environments. Verification needed in production. | Potential cross-session leakage if context propagation fails. | **Monitoring** |
| **C-004** | `api/websocket.py` | ADK 1.26.0 `run_live` events do not easily expose tool results. | **Workaround Implemented**: Side-channel queue with `tool_wrapper` captures and forwards results. | **Fixed (Workaround)** |

## 2. High-Severity Bugs (Verified/Resolved)

| ID | Component | Issue | Impact | Status |
|:---|:---|:---|:---|:---|
| **H-001** | `Dockerfile` | `data/` directory missing. | Resolved: `COPY data/ /app/data/` added. | **Fixed** |
| **H-002** | `frontend/app.js` | XSS vulnerability via `innerHTML`. | Resolved: Using `textContent` and `escapeHtml`. | **Fixed** |
| **H-003** | `frontend/app.js` | `AudioContext` suspension. | Resolved: `initPlayback` called on user gesture. | **Fixed** |
| **H-005** | `services/firestore_eam.py` | Atomic counter increment. | Resolved: Uses Firestore transaction. | **Fixed** |

## 3. Recently Resolved

- **C-001**: `firestore.ArrayUnion` removed from `work_order.py`.
- **C-003**: `asyncio.run_until_complete` removed; all tools are `async def`.
- **C-005**: WebSocket payload alignment between frontend/backend.
- **C-006**: ADK `send_realtime` API fix.
- **C-007**: Gemini model name fix.
- **C-008**: JsonEAM fallback for agent tools.
- **F-004/F-005**: Status filtering and enum normalization.
- **M-007**: DOM growth capping in `app.js`.
- **Transcription Serialization**: Fixed `TypeError` in `websocket.py`.

## 4. Remaining Tasks before Demo

1.  **Mobile Verification**: Test end-to-end on a physical device.
2.  **RULES.md Section 4 Verification**: Perform the full end-to-end checklist.
3.  **Authentication**: (A-001) No auth implemented yet. `ENABLE_AUTH=false` for hackathon.


## 3. Missing Features & UX Gaps

| ID | Component | Issue | Impact |
|:---|:---|:---|:---|
| **M-008** (Fixed) | Frontend Chat | Chat attachment icon did not reliably offer direct camera capture on mobile | Technicians could only pick saved photos in some mobile/PWA contexts |