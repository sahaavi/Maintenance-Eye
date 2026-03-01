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
