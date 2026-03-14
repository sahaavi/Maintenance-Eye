# Bug Report & System Audit — Maintenance-Eye

**Date**: March 13, 2026
**Status**: All Critical and High-Severity Issues Resolved

## Summary

| Severity | Found | Fixed | Remaining |
|:---------|:------|:------|:----------|
| Critical | 8 | 8 | 0 |
| High | 6 | 6 | 0 |
| Medium | 8 | 8 | 0 |
| Monitoring | 1 | — | 1 |

## 1. Resolved Critical Bugs

| ID | Component | Issue | Resolution |
|:---|:---|:---|:---|
| **C-001** | `agent/tools/work_order.py` | `firestore.ArrayUnion` used incorrectly | Removed; uses list append |
| **C-003** | Agent tools | `asyncio.run_until_complete` in async context | All tools converted to `async def` |
| **C-004** | `api/websocket.py` | ADK `run_live` events don't expose tool results | Side-channel queue with `tool_wrapper` captures and forwards results |
| **C-005** | WebSocket | Payload format mismatch between frontend/backend | Aligned message schemas |
| **C-006** | `api/websocket.py` | ADK `send_realtime` API change in v1.10.0 | Changed to single positional argument |
| **C-007** | `agent/maintenance_agent.py` | Gemini model name `gemini-2.5-flash-native-audio` not found | Added `-latest` suffix |
| **C-008** | Agent tools | Agent tools returned empty results when Firestore unavailable | `get_eam_service()` returns `JsonEAM` fallback |
| **C-009** | `agent/tools/work_order.py` | Work order creation allowed without asset_id or description | Required field enforcement at three layers (proposal, tool, confirmation) |

## 2. Resolved High-Severity Bugs

| ID | Component | Issue | Resolution |
|:---|:---|:---|:---|
| **H-001** | `Dockerfile` | `data/` directory missing from container | Added `COPY data/ /app/data/` |
| **H-002** | `frontend/app.js` | XSS vulnerability via `innerHTML` | Uses `textContent` and `escapeHtml`; DOM capped at 120 items |
| **H-003** | `frontend/app.js` | `AudioContext` suspension on iOS/Safari | `initPlayback` called on user gesture |
| **H-005** | `services/firestore_eam.py` | Non-atomic WO ID counter increment | Uses Firestore transaction |
| **H-006** | Search/Agent tools | Spoken/transcribed asset IDs failed to resolve | Added ASR normalization for letter-by-letter and spoken separator forms |
| **H-007** | `services/query_engine.py` | WO search returned 0 results for "open work orders" | Stripped entity meta-words from search tokens; fixed filter fallbacks |

## 3. Resolved Medium Bugs

| ID | Component | Issue | Resolution |
|:---|:---|:---|:---|
| **M-001** | `services/json_eam.py` | `search_work_orders` crash on `None` fields | `or ""` fallback for nullable fields |
| **M-002** | `api/websocket.py` | Duplicate WO creation on confirmation | Confirm handler sends "ALREADY EXECUTED" to agent |
| **M-003** | `api/websocket.py` | Agent thinking text spoken aloud | Suppress non-partial text; filter bold-markdown headers |
| **M-004** | `frontend/app.js` | Transcript words displayed one-per-line | Buffer fragments into speaker-turn bubbles |
| **M-005** | `frontend/app.js` | Raw markdown in chat messages | Safe markdown renderer (escape HTML, then convert) |
| **M-006** | `frontend/app.js` | Inline bullet lists rendered as single paragraph | Pre-normalize inline markers to line-delimited form |
| **M-007** | `frontend/app.js` | Unbounded DOM growth in transcript area | Capped at 120 message items |
| **M-008** | `frontend/app.js` | Chat attach icon unreliable for camera capture on mobile | Explicit camera vs gallery source picker |

## 4. Monitoring

| ID | Component | Issue | Status |
|:---|:---|:---|:---|
| **C-002** | `agent/tools/confirm_action.py` | `ContextVar` may not propagate to ADK tool execution in all environments | No issues observed in production; monitoring |

## 5. Remaining Tasks

1. **Mobile Verification**: Full end-to-end test on a physical device
2. **Authentication**: No auth implemented yet (`ENABLE_AUTH=false` for hackathon)
