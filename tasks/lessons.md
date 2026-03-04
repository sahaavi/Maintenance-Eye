# Lessons Learned — Maintenance-Eye

## 2026-03-02 - JsonEAM search_work_orders NoneType crash

**Context:** WO-2026-0152 has `assigned_to: null` (unassigned). The `search_work_orders` method joins all WO fields for full-text search using `" ".join([...])`.

**Root cause:** `dict.get("assigned_to", "")` returns `None` (not `""`) when the key exists but value is `None`. The `.join()` then fails with `TypeError: sequence item 6: expected str instance, NoneType found`.

**Solution:** Changed all `.get()` calls in the searchable join to use `or ""` fallback: `wo.get("assigned_to", "") or ""`.

**Durable rule:** When building searchable text from optional fields, always use `value or ""` pattern, not just `dict.get(key, "")`, because explicit `None` values bypass the default.

## 2026-03-02 - Duplicate WO Creation from Confirmation Flow

**Problem:** When technician confirmed an action, the system created WO-2026-0004 via `_execute_confirmed_action()`, then the agent created WO-2026-0005 by calling `manage_work_order(action="create")` again.

**Root Cause:** The confirm handler sent "The technician CONFIRMED... Proceed with: {description}" to the agent. The prompt said "If CONFIRMED → execute the action with manage_work_order." The agent interpreted "Proceed with" as an instruction to create the WO, not knowing the system already did it.

**Solution:**
1. Changed confirm/correct handler messages to `[SYSTEM] Action was CONFIRMED and ALREADY EXECUTED... Do NOT call manage_work_order again.`
2. Updated prompt step 6: "the system ALREADY executes the action automatically. Do NOT call manage_work_order again."

**Rule:** When a backend automation executes an action on confirmation, the message to the agent MUST explicitly say "ALREADY EXECUTED" and "Do NOT re-execute." Otherwise the agent will follow its prompt instructions and execute again.

## 2026-03-02 - Gemini Native Audio Thinking Text Suppression

**Problem:** Model speaks internal reasoning aloud ("Prioritizing Safety Protocols", "Establishing Asset Context") and it appears in the UI as transcript text with bold markdown.

**Root Cause:** Gemini 2.5 Flash native audio model has a "thinking" feature that sometimes gets vocalized. The output transcription captures these as partial text events with bold markdown headers (`**...**`).

**Solution:** Two-layer suppression:
1. Non-partial text (pure thinking) → suppressed entirely in live mode (not sent to client)
2. Partial text starting with `**` → filtered out from transcript_output (bold markdown = thinking header pattern)

**Rule:** For native audio models, suppress ALL non-partial text events in live mode (agent communicates via audio only). Additionally filter transcript fragments that match thinking patterns (`**bold headers**`).

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

## 2026-03-02 - Work Order Search Returns 0 Results Due to Entity Meta-Words + Asset ID Handling

**Problem:** "open work orders" returned 0 results despite 42 open WOs. "ESC-SR-001 open wos" returned either the asset itself (not WOs) or 155 WOs (all, not filtered). Chat agent was inconsistent while live agent worked.

**Root Cause (6 compounding bugs):**
1. **NOISE_WORDS missing entity-type words:** "work" and "orders" remained as search tokens → tokenized AND matching failed.
2. **Fallback searches dropped filters:** Both `query_engine.py` and `work_order.py` fallback searches lost status/priority/department.
3. **REST API routing bug:** `routes.py` `has_advanced` was missing `wo_status`.
4. **Intent detection wrong:** "ESC-SR-001 open wos" → asset ID detected → routed to asset search, ignoring WO keywords.
5. **Asset ID short-circuits WO search:** `execute_search()` found asset by ID and returned early, never reaching WO search.
6. **Cache key collision:** Different queries (e.g., "ESC-SR-001 open wos" vs "open work orders") produced same cache key when both had empty normalized_terms + same filters.

**Solution:**
1. Added entity meta-words to NOISE_WORDS: "work", "order", "orders", "wo", "wos", "ticket", "asset", "equipment", "report", "inspection", etc.
2. Fallback searches pass all original filters.
3. Added `wo_status` to `has_advanced` check.
4. Intent detection: when asset ID + WO keywords coexist, prefer `work_order` intent.
5. `execute_search()`: skip asset ID lookup when intent is `work_order`; let WO search include asset ID as text filter.
6. Cache key now includes `extracted_ids`.
7. `_search_work_orders()` and `work_order.py` search action now re-include extracted asset IDs in search text.

**Rules:**
- Entity-type descriptor words MUST be stripped from search text (NOISE_WORDS).
- Fallback searches MUST preserve all filters from the original query.
- When an asset ID and WO keywords coexist, intent must be `work_order`, not `asset`.
- ID lookup in `execute_search` must respect intent — don't return an asset when user wants work orders.
- Cache keys must include ALL query discriminants (intent, terms, IDs, filters).

---

## 2026-03-01 - Intelligent Search Pre-Query Layer

**Context:** Agent tools passed raw user queries directly to EAM service — no normalization, no alias resolution, no synonym expansion. "wo 10234" wouldn't find WO-2025-10234, "critical open" wouldn't map to P1+open filters.

**Problem:** Technician natural language didn't match the rigid search interface. The agent had to make multiple tool calls or guess parameters.

**Solution:** Created `QueryEngine` (`backend/services/query_engine.py`) as a pre-query intelligence layer:
1. **Intent detection** — regex for ID formats + keyword triggers route to the right entity type
2. **ID normalization** — partial IDs padded and year-prefixed (e.g., "wo 0008" → WO-2025-0008)
3. **Filter extraction** — priority/status/department/asset_type aliases resolved from natural language tokens
4. **Synonym expansion** — domain symptom terms expand to related search terms + EAM codes
5. **Result ranking** — exact ID = 1.0, name match = 0.8-0.9, description = 0.7, expanded = 0.3
6. **TTL cache** — 60s cache avoids repeated Firestore round-trips

Also fixed `manage_work_order` search action which had department hardcoded to `""`, and added missing `get_work_order(wo_id)` direct lookup to the EAM interface.

**Rule:** Any search tool exposed to an AI agent needs a normalization layer between the agent and the database. Agents produce informal, variable input — the normalization layer makes the database interface tolerant of that variability.

## 2026-03-01 - Live Audio Transcript Display: Buffer Fragments

**Problem:** Gemini Live API sends `transcript_input` / `transcript_output` events as small word-level fragments. Creating a new `<div>` per fragment causes each word to appear on its own line — looks broken.

**Root Cause:** The `addTranscript()` function treated each event as a complete message. But in Live API streaming, transcripts arrive incrementally (like real-time closed captioning).

**Solution:** Buffer transcript fragments into a single `<span>` per speaker turn:
1. Track `currentTranscriptEl` and `currentTranscriptSpeaker` in state
2. If same speaker, append text to existing `<span class="transcript-text">`
3. If different speaker or 3s silence, finalize the bubble and start a new one
4. Also finalize on interruption or tool_call events (natural turn boundaries)

**Rule:** Streaming transcript APIs always produce fragments. Never create a new DOM element per fragment. Always buffer with a speaker-change + timeout flush strategy. Industry standard: 2-4s silence timeout.

## 2026-03-01 - AI Agent Context Retention in Live Audio Sessions

**Problem:** Agent heard "Scott Road escalator" early in session but when user said "close the work order" later, agent couldn't find the WO because it didn't carry the asset context forward.

**Root Cause:** The system prompt didn't explicitly instruct the model to retain and reuse context from earlier in the conversation when performing searches.

**Solution:** Added "Context Retention & Proactive Search" section to both SYSTEM_PROMPT and CHAT_SYSTEM_PROMPT with rules:
- Remember asset/station/WO mentions from entire conversation
- Search proactively with available context rather than demanding exact IDs
- Try multiple search strategies before saying "can't find it"

**Rule:** LLM agents in conversational sessions need explicit prompt instructions to carry forward entity context. The model won't automatically use earlier mentions in tool calls unless told to.

## 2026-03-02 - Knowledge Base Search Requires Meta-Word Stripping

**Problem:** "signal controller cabinet inspection protocol" returned 0 results despite KB-007 "Signal Controller Cabinet Inspection" being an exact match.

**Root Cause:** Two compounding bugs:
1. `search_knowledge_base()` used whole-phrase substring matching (`ql in searchable`), not tokenized.
2. Even after fixing to tokenized AND matching, the word "protocol" isn't in KB-007 anywhere (title, content, or tags). Tokenized AND requires ALL tokens present.

**Solution:** Strip "document-type meta words" (protocol, procedure, manual, guide, checklist, etc.) from KB queries before matching. These words describe what the user wants, not the content itself. Applied to both JsonEAM and FirestoreEAM.

**Rule:** Knowledge base search must strip meta/intent words before matching. A user searching for "escalator handrail inspection procedure" wants the document ABOUT escalator handrails, not one containing the literal word "procedure".

## 2026-03-02 - ADK Event.partial for Transcript vs Text Routing

**Problem:** `hasattr(event, "output_transcription")` in websocket.py was dead code — ADK Event has no such attribute. Transcription fragments arrived as `event.content.parts[0].text` with `event.partial=True`, were sent as `type: "text"`, and each word created a new bubble.

**Root Cause:** Misunderstanding of ADK event model. Transcription comes through the same `content.parts[0].text` path as regular text responses. The `partial` field on Event/LlmResponse distinguishes fragments from complete responses.

**Solution:** Check `getattr(event, 'partial', False)` in the `part.text` handler. Partial → `transcript_output`/`transcript_input`. Non-partial → `text`. Remove dead `hasattr` blocks.

**Rule:** In ADK Live API: `event.partial=True` = transcription fragment, `event.partial=False` = complete text response. Never use `hasattr(event, "output_transcription")` — that attribute doesn't exist on Event.

## 2026-03-03 - Required Field Enforcement Must Be Multi-Layered for Work Order Creation

**Context:** Work-order creation was previously allowed with empty `asset_id` and/or `description` in the creation tool and in auto-execution after confirmation.

**Root Cause:** Validation relied mostly on agent behavior and confirmation flow conventions, with no hard guardrails at every execution entry point.

**Solution:** Added required-field checks at three layers:
1. `propose_action` blocks incomplete `create_work_order` proposals.
2. `manage_work_order(action="create")` rejects missing `asset_id`/`description` with `missing_fields`.
3. `_execute_confirmed_action` in websocket path rejects confirmed create actions missing the same fields.

**Rule:** For safety-critical create flows, enforce required inputs in every executable backend path (proposal, tool execution, and post-confirmation automation), not only in prompts.

## 2026-03-03 - Sync Tool Wrappers That Schedule Async Tasks Need Event Loop-Aware Tests

**Context:** New `propose_action` unit tests initially failed with `RuntimeError: no running event loop`.

**Root Cause:** The `tool_wrapper` for sync tools schedules `_capture_result` via `asyncio.create_task()`, which requires a running event loop even when the tool itself is synchronous.

**Solution:** Marked the tests as async (`@pytest.mark.asyncio`) so they execute inside an event loop.

**Rule:** When testing wrapped sync tools that call `asyncio.create_task`, run tests in an async pytest context rather than plain synchronous test functions.
