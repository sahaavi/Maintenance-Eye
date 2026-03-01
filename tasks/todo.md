## Enterprise Data Explorer Redesign - 2026-03-01

**Scope:**
- Component(s): backend/api/routes.py, backend/services/eam_interface.py, backend/services/json_eam.py, backend/services/firestore_eam.py, frontend/index.html, frontend/style.css, frontend/app.js, frontend/sw.js
- Risk Level: Medium (EAM interface additions, new REST endpoints, full frontend dashboard rewrite)
- Dependencies: seed_data.json for JSON fallback, existing EAMService interface

**Checklist:**
- [x] Add `search_work_orders()` method to EAMService abstract interface
- [x] Add `get_locations()` method to EAMService abstract interface
- [x] Implement both methods in JsonEAM (full-text search on id/description/equipment, filter by priority/department/location)
- [x] Implement both methods in FirestoreEAM (Firestore-backed queries with filters)
- [x] Add `GET /api/work-orders` enhanced with `q`, `priority`, `department`, `location`, `limit` query params
- [x] Add `GET /api/locations` endpoint returning unique location strings from assets
- [x] Replace single-tab dashboard with 5-page layout: Work Orders, Assets, Locations, Knowledge Base, EAM Codes
- [x] Add sidebar nav (desktop) and bottom nav (mobile) with active state management
- [x] Add filter bars per page (dropdowns for priority/dept/location, debounced search input)
- [x] Build table renderers for Work Orders and EAM Codes pages
- [x] Build card/grid renderers for Assets, Locations, Knowledge Base pages
- [x] Bump SW cache to v3, HTML asset query params to v4
- [x] Verify all 5 API endpoints return data (tested via curl/browser)
- [ ] Deploy to GCP Cloud Run and verify on mobile device
- [ ] Run end-to-end verification checklist (Section 4 of RULES.md)

---

## Fix Inspection Flow + Deploy to GCP - 2026-02-28

**Scope:**
- Component(s): frontend/app.js, frontend/style.css, backend/api/websocket.py, backend/config.py, backend/services/, cloudbuild.yaml
- Risk Level: Medium (EAM interface change, WebSocket protocol fix, deployment config)
- Dependencies: Gemini API key, GCP project, seed_data.json

**Checklist:**
- [x] Fix dashboard screen always visible (CSS `#dashboard-screen` had `display:flex` overriding `.screen` display:none)
- [x] Fix back button on Data Explorer (same root cause as above)
- [x] Add camera/mic failure feedback on splash screen
- [x] Disable auth in production deployment (`ENABLE_AUTH=false` in cloudbuild.yaml)
- [x] Add Cloud Run WebSocket timeout (`--timeout=3600`) and session affinity
- [x] Bump service worker cache version and asset query params for cache busting
- [x] Fix ADK `LiveRequestQueue.send_realtime()` API — changed from keyword args to positional `blob` param in ADK 1.10.0
- [x] Fix Gemini Live model name — `gemini-2.5-flash-native-audio-latest` (not `gemini-live-...` or without `-latest`)
- [x] Fix dual API key warning — move GEMINI_API_KEY to GOOGLE_API_KEY, remove duplicate
- [x] Fix Pydantic enum warning — use `types.Modality.AUDIO` instead of string `"AUDIO"`
- [x] Fix Firestore `.where()` deprecation — migrate to `FieldFilter` syntax
- [x] Downgrade GCS upload failure log to debug (expected without bucket)
- [x] Create `JsonEAM` fallback for agent tools when Firestore unavailable
- [x] Update `get_eam_service()` to try Firestore first, fall back to JsonEAM
- [x] Remove `firestore.ArrayUnion` dependency from `work_order.py` tool
- [ ] Catch up on RULES.md compliance (tasks/todo.md, tasks/lessons.md, bug tracking)
- [ ] Deploy to GCP Cloud Run and verify on mobile device
- [ ] Run end-to-end verification checklist (Section 4 of RULES.md)

---

## Review - Fix Inspection Flow + Deploy to GCP

**What Worked:**
- JsonEAM fallback approach — implements same EAMService interface, all 8 tools benefit without touching tool files
- Fixing `get_eam_service()` at the singleton level was the right abstraction point
- ADK API investigation via Python introspection (`inspect.signature`) was fast and reliable

**What Didn't:**
- Model name required trial-and-error (API listing didn't show `bidiGenerateContent` in supported methods)
- CSS specificity bug was non-obvious — ID selector silently overrode class-based visibility
- Didn't follow RULES.md workflow (no plan mode, no todo tracking, no lessons captured during iteration)

**Production Readiness:**
- [ ] Load tested with concurrent sessions
- [ ] Tested on iOS Safari + Android Chrome
- [ ] Error handling covers all tool failure modes
- [ ] Logging sufficient for debugging in Cloud Run
