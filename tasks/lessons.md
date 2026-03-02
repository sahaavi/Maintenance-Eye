# Lessons Learned — Maintenance-Eye

## 2026-03-01 - EAM Interface Extension Pattern

**Context:** Added `search_work_orders()` and `get_locations()` to support richer dashboard filtering.

**Pattern that worked:** Extend the `EAMService` abstract base class first, then implement in both `JsonEAM` and `FirestoreEAM`. The abstract base ensures both backends stay in sync. JsonEAM uses in-memory filtering; FirestoreEAM uses `FieldFilter` queries.

**Key detail for JsonEAM search:** Full-text search over work orders must cover `id`, `description`, and `equipment_id` fields (all lowercased). Priority and department filters are exact match; location filter is substring match on the asset's location looked up via asset_id cross-reference.

**Rule:** When adding EAM service methods, always implement in this order: (1) abstract interface, (2) JsonEAM with seed_data fallback, (3) FirestoreEAM. Test each independently via the REST API before wiring to agent tools.

---

## 2026-03-01 - Multi-Page Dashboard Without a Build System

**Context:** Replaced a single-tab dashboard with a 5-page enterprise layout in a vanilla JS PWA (no React, no bundler).

**Pattern:** Use a single-page architecture with CSS `display:none`/`display:block` toggling. Each "page" is a `<section>` with a shared `data-page` attribute. JavaScript keeps one `currentPage` variable and calls `loadPage(name)` to fetch+render data on navigation. Sidebar highlights the active item with a class swap.

**Pitfall avoided:** Do NOT apply `display:flex` directly on page `id` selectors — it will override the `.page.active` pattern. Always qualify: `#work-orders-page.active { display: flex }` or rely purely on class-based rules.

**Cache busting rule confirmed:** SW cache version AND HTML `?v=` query params must both be bumped on every deploy that touches frontend files. This session: SW → v3, HTML params → v4.

**Rule:** For vanilla JS multi-page dashboards, use data-attribute page routing + class-based visibility. Never set `display` on bare ID selectors when a class toggle controls visibility.

---

## 2026-03-01 - Debounced Search in Vanilla JS

**Pattern:** Use a module-level `let searchTimeout = null` variable. On every `input` event: `clearTimeout(searchTimeout); searchTimeout = setTimeout(() => loadPage(currentPage), 300)`. This avoids firing an API call on every keystroke.

**Rule:** Any search input wired to a network call needs debouncing. 300ms is the standard delay for a responsive feel without hammering the API.

---

## 2026-02-28 - ADK LiveRequestQueue API Change (v1.10.0)

**Problem:** `LiveRequestQueue.send_realtime()` raises `TypeError: got an unexpected keyword argument 'audio'`

**Root Cause:** ADK 1.10.0 changed the signature from `send_realtime(audio=blob)` / `send_realtime(video=blob)` to a single positional parameter `send_realtime(blob)`. Both audio and video blobs go through the same param.

**Solution:**
```python
# Before (broken in ADK 1.10.0)
live_request_queue.send_realtime(audio=audio_blob)
live_request_queue.send_realtime(video=video_blob)

# After
live_request_queue.send_realtime(audio_blob)
live_request_queue.send_realtime(video_blob)
```

**Rule:** Always check ADK method signatures with `inspect.signature()` when upgrading. ADK is pre-1.0 and breaking changes are common.

---

## 2026-02-28 - Gemini Live API Model Names

**Problem:** `models/gemini-2.5-flash-native-audio is not found for API version v1alpha`

**Root Cause:** The model ID `gemini-2.5-flash-native-audio` doesn't resolve. The API requires the explicit `-latest` suffix. The old `gemini-live-*` prefix format is also invalid.

**Solution:**
```python
# Wrong
GEMINI_LIVE_MODEL = "gemini-live-2.5-flash-native-audio"  # old prefix
GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio"        # missing suffix

# Correct
GEMINI_LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"
```

**Verification method:** Test with `client.aio.live.connect(model=name)` — a "Cannot extract voices" error means the model exists (just needs config). A "not found" error means wrong name.

**Rule:** Always use explicit version suffixes (`-latest`, `-preview-12-2025`) for Gemini Live API models. Never assume short names resolve.

---

## 2026-02-28 - CSS ID Selector Specificity Override

**Problem:** Dashboard screen always visible. Back button "doesn't work." Splash screen hidden behind dashboard.

**Root Cause:** `#dashboard-screen { display: flex }` (ID selector) overrides `.screen { display: none }` (class selector) due to CSS specificity. The `active` class toggle had no effect.

**Solution:**
```css
/* Before (broken) — always visible */
#dashboard-screen { display: flex; ... }

/* After — only visible when active */
#dashboard-screen.active { display: flex; ... }
```

**Rule:** When using class-based visibility patterns (`.screen` / `.screen.active`), never set `display` on ID selectors. Or use the same `.active` qualifier on ID-scoped rules.

---

## 2026-02-28 - Agent Tools vs REST API Data Access Gap

**Problem:** Agent (Max) says "I can't find any assets" but dashboard shows data fine.

**Root Cause:** REST API routes (`routes.py`) fall back to `seed_data.json` when Firestore is unavailable. Agent tools call `get_eam_service()` which returns `FirestoreEAM` — which silently returns empty results when Firestore has no data or isn't reachable.

**Solution:** Created `JsonEAM` (implements `EAMService` interface) backed by `seed_data.json`. Updated `get_eam_service()` to return `JsonEAM` when Firestore isn't configured (no emulator, not production).

**Rule:** Any data access path used by agent tools MUST have the same fallback behavior as the REST API. The EAM abstraction layer (`get_eam_service()`) is the right place to handle this — not individual tool files.

---

## 2026-02-28 - RunConfig response_modalities Enum

**Problem:** `PydanticSerializationUnexpectedValue: Expected 'enum' for response_modalities`

**Root Cause:** ADK `RunConfig.response_modalities` expects `types.Modality` enum values, not plain strings.

**Solution:**
```python
# Before
response_modalities=["AUDIO"]

# After
from google.genai import types
response_modalities=[types.Modality.AUDIO]
```

**Rule:** Always use genai `types.*` enums for ADK config fields, not string literals.

---

## 2026-02-28 - Firestore .where() Deprecation

**Problem:** `UserWarning: Detected filter using positional arguments`

**Root Cause:** Firestore Python SDK deprecated positional `.where("field", "==", value)` in favor of the `filter=` keyword.

**Solution:**
```python
# Before
ref.where("department", "==", department)

# After
ref.where(filter=firestore.FieldFilter("department", "==", department))
```

**Rule:** Always use `filter=firestore.FieldFilter(...)` syntax for Firestore queries.

---

## 2026-02-28 - Service Worker Cache Busting

**Problem:** Deployed fixes not visible to returning users — browser serves stale CSS/JS from service worker cache.

**Solution:** Bump `CACHE_NAME` version in `sw.js` AND asset query params in `index.html` (`?v=3`) on every deploy that changes frontend files.

**Rule:** Any frontend change must bump both the SW cache name and HTML asset version params.

## 2026-03-01 - Native Audio Model Cannot Use TEXT Response Modality

**Context:** Added chat WebSocket endpoint with `response_modalities=[types.Modality.TEXT]` for text-only chat mode.

**Problem:** The `gemini-2.5-flash-native-audio-latest` model is designed for audio I/O. Setting TEXT-only response modality causes the model to not respond to `send_content()` text messages — it expects audio turn-taking signals.

**Solution:** Always use `response_modalities=[types.Modality.AUDIO]` with native audio models. For text-mode chat, ignore the audio data on the frontend and display `transcript_output` (the automatic speech-to-text transcription of the agent's audio response) as the text message instead.

**Rule:** Native audio Gemini models (`*-native-audio-*`) must always use AUDIO response modality. For text chat, use a separate agent with a text model (`gemini-2.5-flash`) and `runner.run_async()` instead of `run_live()`. This gives clean text responses without transcription artifacts.

## 2026-03-01 - Stale Fallback Code After Refactoring

**Context:** EAM codes endpoint had a manual `_load_json()` fallback from before the `get_eam_service()` singleton refactor.

**Problem:** `_load_json` was never defined in `routes.py` — it was removed during the singleton refactor but the `except` clause still referenced it, causing `NameError` on any empty Firestore response.

**Solution:** Removed the redundant try/except fallback. The `get_eam_service()` singleton already handles Firestore → JsonEAM fallback transparently.

**Rule:** After refactoring to a unified service layer, remove all manual fallback code in route handlers. The service layer IS the fallback.

## 2026-03-02 - Network-Restricted Test Dependency Installation

**Context:** Implemented a full automated test architecture with new test dependencies (`pytest`, `playwright`, quality/security tooling) and attempted local verification.

**Problem:** `python3 -m pip install -r backend/requirements-dev.txt` failed because the environment cannot reach package indexes (DNS/network restriction), so runtime verification commands could not execute.

**Root Cause:** Assumed external package installation would be available during local validation.

**Solution:**
- Kept the test suite deterministic and fully committed with executable scripts and CI workflow.
- Validated syntax deterministically with `python3 -m compileall tests`.
- Shifted full execution responsibility to network-enabled environments (developer machine with internet or CI runner).

**Rule:** Before depending on new Python packages for local verification, check install/network capability early; if blocked, provide compile-time validation plus CI-ready execution paths.

## 2026-03-02 - Asset Search Must Use Tokenized Matching

**Context:** User asked chat agent about "Gateway Hvac Unit #2". Agent called `lookup_asset(query="Gateway Hvac Unit #2")` but got no results. After listing ALL work orders, the agent found the work order mentioning that exact asset name.

**Problem:** `search_assets()` used contiguous substring matching (`query.lower() in searchable`). The agent sometimes sends slightly different phrasing or adds department filters that narrow results incorrectly. Additionally, the searchable string only covered `name`, `asset_id`, and `station` — missing `type`, `department`, `manufacturer`, `model`, `equipment_code`, and `asset_hierarchy`.

**Root Cause:** Contiguous substring matching fails when word order differs or extra context words are added. The agent had to fall back to listing all work orders (150+) and scanning manually.

**Solution:**
1. Changed `search_assets()` in both `JsonEAM` and `FirestoreEAM` to use **tokenized word matching**: split query into words, check that ALL words appear anywhere in the searchable text.
2. Expanded searchable fields to include `type`, `department`, `equipment_code`, `manufacturer`, `model`, `zone`, and `asset_hierarchy`.
3. Applied same tokenized matching to `search_work_orders()` in both backends.
4. Added `"search"` action to `manage_work_order` tool so the agent can search work orders by text query instead of listing all.
5. Improved `lookup_asset` docstring to tell the agent the search is tokenized and to try broader queries if first search fails.

**Rule:** All text search in EAM services must use tokenized word matching (`all(token in searchable for token in query.split())`), not contiguous substring matching. Search fields must cover all human-readable attributes of the entity.

## 2026-03-02 - Mobile Chat Attach Should Offer Explicit Source Selection

**Context:** Chat attach icon used a single file input (`accept=\"image/*\" capture=\"environment\"`). On some mobile/browser combinations, this only exposed saved photos and did not reliably present direct camera capture.

**Problem:** Field users could not quickly capture a fresh fault photo from the chat flow.

**Root Cause:** Relying on browser interpretation of a single `capture` file input is inconsistent across devices/PWA contexts.

**Solution:** Added an explicit in-chat source picker with two actions:
- `Take Photo` -> hidden input with `capture=\"environment\"`
- `Choose Photo` -> hidden input without `capture`
Both paths continue through the same preview and WebSocket image send pipeline.

**Rule:** For mobile file capture UX, avoid relying on one `capture` input. Provide explicit camera vs gallery choices and keep a shared downstream image handling path.
