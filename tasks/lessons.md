# Lessons Learned — Maintenance-Eye

## 2026-03-05 - Multi-Word Asset Types Must Suppress Conflicting Department Filters

**Context:** Query "open work order for Metrotown Track Circuit 3" returned 0 results despite WO-2025-0006 existing. The word "track" triggered `department=guideway` via `DEPARTMENT_ALIASES`, while "track circuit" also set `asset_type=track_circuit`. Both filters applied independently, but TRC-MT-003 is `department=signal_telecom`, so the guideway filter excluded it.

**Root Cause:** `_extract_filters()` applied department and asset_type detection independently. When a word (e.g., "track") appeared in both a multi-word asset_type phrase ("track circuit") and the department alias map, it created conflicting filters.

**Solution:** After asset_type extraction, collect the constituent words of matched multi-word phrases. During department single-token matching, if the matched department token is part of an asset_type phrase, remove the department filter to avoid the conflict.

**Rule:** When NLP filter extraction detects both department and asset_type from overlapping tokens, the more specific filter (asset_type from a multi-word phrase) must win. Never let a single word simultaneously drive two conflicting filters.

## 2026-03-05 - Compound-Word Matching Handles ASR Name Splitting

**Context:** "Metro Town" (2 words from ASR) vs "Metrotown" (1 word in DB). The token "metro" matched via prefix, but "town" had no match — AND-logic failed the entire query.

**Root Cause:** `query_matches_text()` only tried individual token matching. When ASR splits a compound proper noun into parts, each part may not independently match any searchable token.

**Solution:** Added a compound-word pass in `query_matches_text()`: for unmatched alpha tokens, try concatenating with the adjacent token (including previously matched ones). If the compound matches a searchable token exactly or via prefix, both tokens are marked matched. Also added bigram-based fuzzy matching (Dice coefficient >= 0.6) as a last resort for ASR garbling (e.g., "downtrex" ≈ "downtown").

**Rule:** Text matchers in speech-driven search must handle compound-word splitting. After individual token matching, try concatenating adjacent unmatched tokens before declaring no match. Add fuzzy fallback only for tokens >= 5 chars to avoid false positives.

## 2026-03-05 - WO Search Needs Relaxed-Filter Fallback Like Asset Search

**Context:** `_search_assets()` had a relaxed-filter fallback when NLP-derived filters over-constrained results, but `_search_work_orders()` had no equivalent — wrong department meant 0 results with no recovery.

**Solution:** Added the same pattern to `_search_work_orders()`: when primary search returns 0 results AND filters were applied (department/location/priority), retry with just `q` + `status`. Score relaxed results slightly lower (-0.05).

**Rule:** Every search function that accepts NLP-derived filters must have a relaxed-filter fallback. NLP filter extraction is inherently noisy — the fallback ensures users still get results when filters are wrong.

## 2026-03-05 - Shared Base Class Eliminates EAM Search Duplication

**Context:** `JsonEAM` and `FirestoreEAM` had near-identical implementations of searchable string construction (asset: 11-field join, WO: 10-field join), location/department filter resolution, station aggregation, and KB meta-word stripping — ~90 lines duplicated across both files.

**Root Cause:** `BaseEAMService` was created but only contained `normalize_work_order_updates()`. All search logic was copy-pasted into each concrete implementation.

**Solution:** Extended `BaseEAMService` with 6 shared static/class methods:
- `build_asset_searchable(asset)` — 11-field searchable string
- `build_wo_searchable(wo, asset)` — 10-field searchable string with null safety
- `resolve_location_dept_filters(assets_iter, location, dept)` — returns asset_id sets
- `aggregate_stations(assets_iter)` — station grouping with counts
- `tokenize_kb_query(query)` — meta-word stripping for KB search
- `kb_tokens_match(tokens, searchable)` — all-tokens-present check

Both `JsonEAM` and `FirestoreEAM` now delegate to these shared methods.

**Rule:** When two EAM backends share identical text-matching or aggregation logic, extract it to `BaseEAMService` as a static/classmethod. The concrete classes should only contain storage-specific operations (Firestore queries, in-memory dict access).

## 2026-03-05 - ASR Domain Terms Need Explicit Correction Map

**Context:** Speech-to-text garbles domain terms like "VOBC" into "V OBC", "OVC", "BOBC", etc. The `_detect_train_subsystem_suffix()` only checked exact `"vobc"` string, so ASR variants were never resolved to the correct subsystem suffix.

**Root Cause:** No fuzzy/ASR correction step existed before ID extraction. The pipeline assumed clean text input.

**Solution:**
1. Added `_ASR_CORRECTIONS` map (sorted longest-key-first for greedy matching) applied at the top of `build_query()`, `_extract_ids()`, and `normalize_asset_id()`.
2. Updated `_detect_train_subsystem_suffix()` and `_extract_spoken_tc_ids()` to check ASR variant tokens directly.
3. Added ASR variant entries to `ASSET_TYPE_ALIASES` and `search_matcher.py` `_DOMAIN_CORRECTIONS`.

**Durable Rule:** When adding new domain-specific terms, always add known ASR misrecognition variants to `_ASR_CORRECTIONS` and relevant alias maps.

## 2026-03-05 - Optional Regex Groups Cause NoneType Crashes

**Context:** `_ASSET_ID_PATTERN` has an optional station code group `(?:([A-Z]{2})[-\s])?`. When this group doesn't match, `m.group(2)` returns `None`. The code `m.group(2).upper()` crashed with `AttributeError: 'NoneType' object has no attribute 'upper'`.

**Root Cause:** Pre-existing bug masked because the specific input patterns (like "tc-229") were never tested through this code path until ASR corrections made them possible.

**Solution:** Guard against `None` group values before calling `.upper()` on optional regex groups.

**Durable Rule:** Always check optional regex capture groups for `None` before calling methods on them.

## 2026-03-05 - Pre-Resolve Asset IDs Before WO Search

**Context:** When user says "work orders for RC 139", the system searched work orders with raw "RC-139" which doesn't exist as an asset. The suggestion flow only triggered AFTER the search returned 0 results, requiring an extra round-trip.

**Root Cause:** `_search_work_orders()` used extracted IDs directly without verifying they correspond to real assets.

**Solution:** Added pre-resolution step in `_search_work_orders()`: for each non-WO extracted ID, verify via `eam.get_asset()`, and if not found, use `suggest_asset_candidates()` to find high-confidence (>= 0.7) alternatives and substitute them into the search.

**Durable Rule:** When search depends on entity references (like asset IDs in WO search), verify the referenced entities exist before searching, and auto-resolve when high-confidence alternatives are available.

## 2026-03-05 - Zero-Result WO Search Must Distinguish "No Work Orders" vs "Wrong Asset ID"

**Context:** User query `are there any work order for rc 139` returned zero results and the agent answered as if `RC-139` were a real asset, instead of asking for confirmation or correcting the ID.

**Root Cause:** Search pipeline treated malformed ID text as generic tokens and returned an empty work-order list with no correction metadata. The agent had no structured signal that the asset hint itself might be invalid or close to a known ID.

**Solution:**
1. Added shorthand/malformed asset hint extraction (`RC-139`) and candidate mapping in `QueryEngine`.
2. Added `suggest_asset_candidates()` scoring (number match + prefix similarity) to propose likely assets (for example, `TC-139`).
3. Updated `manage_work_order(search)` and `smart_search` to emit:
   - `needs_asset_confirmation` + `guessed_assets` when likely matches exist.
   - `no_asset_match` when no asset corresponds to the hinted ID.
4. Updated prompts so the agent must ask user confirmation on guessed assets before proceeding.

**Rule:** For safety-critical maintenance search, a zero-result query with an ID-like hint must never be treated as definitive. Return explicit confirmation/no-match metadata so the agent can verify asset identity with the technician before concluding.

## 2026-03-05 - Spoken/Transcribed Asset IDs Need Canonical Parsing Before Search

**Context:** Users reported that chat/live search often missed asset IDs and related work orders. Deterministic probes showed failures for ASR-style phrasing such as `e s c s c 0 0 3`, `e s c dash s c dash zero zero three`, and `t c one three eight prop`.

**Root Cause:** QueryEngine only recognized contiguous ID forms (`ESC-SC-003`, `esc sc 003`, `TC-138-PROP`). When ASR split IDs letter-by-letter or used spoken separators (`dash`) + number words, ID extraction failed. Search then fell back to tokenized AND matching where leftover single-digit fragments (`0`, `3`, `1`, `8`) became mandatory tokens, producing false "no results."

**Solution:**
1. Added spoken-ID parsing for letter-by-letter and dash-word forms in `QueryEngine`.
2. Extended `normalize_asset_id()` to resolve spoken/transcribed formats.
3. Added post-cleaning term pruning to remove digit-by-digit ASR artifacts once an asset ID is extracted.
4. Added noise tokens for spoken punctuation words (`dash`, `hyphen`, `minus`, `number`) and regression tests across query engine + tool paths.

**Rule:** In speech-driven maintenance workflows, never rely only on regex for contiguous IDs. Always normalize ASR-transcribed ID patterns (single-letter sequences, spoken separators, number words) to canonical IDs before text matching.

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

## 2026-03-04 - Markdown Rendering Requires Safe HTML Conversion in Message UIs

**Context:** Agent responses in live inspection and chat displayed raw markdown markers (`**`, `*`) instead of formatted output, reducing readability of severity labels and EAM code lists.

**Root Cause:** Message rendering paths (`addAgentMessage`, `addChatMessage`, transcript updates) used `textContent`, which escapes markdown syntax as literal text.

**Solution:** Added a constrained markdown renderer in `frontend/app.js` that first escapes HTML, then applies inline markdown (`**bold**`, `*italic*`) and line-based bullet list parsing (`-`/`*` list items). Wired assistant output paths to `innerHTML` from this renderer, while preserving plain `textContent` for user-entered text.

**Rule:** If assistant text needs markdown formatting in the UI, never render raw model output with `textContent`; use a safe pipeline: escape HTML first, then transform allowed markdown syntax to HTML.

## 2026-03-04 - Validate Maintenance Scripts Side Effects Before Keeping Output

**Context:** Ran `scripts/manage_bugs.py add ...` while closing a frontend markdown rendering bug.

**Root Cause:** Assumed the script would append a visible bug entry safely; in this repository state it produced an unintended metadata-only edit path and a non-actionable update attempt (`M-009` not found).

**Solution:** Reverted `BUG_REPORT.md` fully to `HEAD` and kept this task scoped to the requested frontend fix.

**Rule:** When using repository maintenance scripts during unrelated bug fixes, inspect `git diff` immediately and discard script side effects unless they are complete, correct, and in-scope for the user request.

## 2026-03-04 - Inline Markdown Lists Need Pre-Normalization Before Rendering

**Context:** Chat responses can include list markers inline in a single sentence (for example: `...: * **WO-1** ... * **WO-2** ...`) instead of line-separated markdown bullets.

**Root Cause:** The markdown renderer only recognized list items when `*`/`-` started a new line. Inline bullet markers stayed inside one paragraph, and italic regex could partially consume `* ...` sequences, making output look bundled and hard to read.

**Solution:** Added a markdown normalization step (`normalizeMarkdownBlocks`) that inserts line breaks before inline bullet/numbered markers after sentence punctuation, then parsed both unordered and ordered lists. Also tightened italic conversion so `* text` (bullet marker pattern) is not treated as emphasis.

**Rule:** For assistant-rendered markdown in streaming/chat UIs, normalize compact inline list markers into line-delimited form before parsing markdown; otherwise bullet-heavy operational summaries will collapse into unreadable blocks.

## 2026-03-04 - `manage_bugs.py` Is Not Compatible With Current `BUG_REPORT.md` Layout

**Context:** Tried to log a newly resolved frontend readability bug with `python3 scripts/manage_bugs.py add ...` followed by `update ...`.

**Root Cause:** The script reported `Added bug M-009`, but only edited aggregate metadata and could not find `M-009` on update (`Bug ID M-009 not found`). The current report structure is not reliably parseable by the script.

**Solution:** Reverted all `BUG_REPORT.md` side effects to `HEAD` and kept the fix scoped to frontend rendering + workflow logs.

**Rule:** Until `manage_bugs.py` parsing is aligned with `BUG_REPORT.md`, run it only with immediate diff inspection and revert output if it does not create/update concrete bug entries deterministically.

## 2026-03-04 - Deployment Scripts Should Not `source` CRLF `.env` Files Directly

**Context:** Running `set -a; source .env; ...` before deployment produced `$'\r': command not found` errors in this repository.

**Root Cause:** `.env` uses CRLF line endings, so direct shell `source` parsing in bash treats carriage returns as command suffixes.

**Solution:** Extract required values with `grep/cut/tr` and strip `\r` + quotes before invoking deployment scripts.

**Rule:** For deployment automation, parse `.env` defensively (`tr -d '\\r"'`) instead of sourcing directly unless line endings are guaranteed LF-only.

## 2026-03-04 - Cloud Deployment from Sandbox Requires Early Escalation

**Context:** Initial deploy attempt failed at `gcloud config set project` with DNS/auth refresh errors in sandbox.

**Root Cause:** Sandbox execution blocked outbound DNS/network required for OAuth token refresh and GCP API calls.

**Solution:** Re-ran deployment with escalated permissions; Cloud Build and Terraform then completed successfully.

**Rule:** Any command that performs live GCP deployment (`gcloud`, `terraform apply`, Cloud Build submit) should be escalated immediately when sandbox network restrictions are active.

## 2026-03-04 - Natural-Language WO Queries Need Filler/Number Normalization + Token-Aware Matching

**Context:** Queries like "is there any open work order for escalator three at Stadium Chinatown" intermittently returned no open work orders even though the correct equipment was recognized.

**Root Cause:** Two combined failures:
1. Query normalization left conversational filler words (`there`, `any`, `do`, `have`) as mandatory AND-match tokens.
2. Spoken numbers (`three`) were not normalized to digits and single-digit terms were dropped.
Additionally, Firestore WO search could crash when nullable fields (e.g., `assigned_to: null`) were concatenated for matching.

**Solution:** 
- Expanded QueryEngine noise terms and normalized number words to digits.
- Preserved numeric single-character tokens in cleaned terms.
- Added asset-ID extraction for spaced formats (`esc sc 003`).
- Replaced substring matching with shared token-aware matcher (`query_matches_text`) in JsonEAM and FirestoreEAM, including numeric equivalence (`3`/`003`/`0003`).
- Made Firestore WO searchable text null-safe with `or ""` fallbacks.

**Rule:** For speech-driven enterprise search, never rely on raw substring AND matching. Always normalize conversational filler + spoken numbers first, then match against canonical tokens with numeric equivalence and null-safe field handling.

## 2026-03-04 - Generic Asset-Type Filters Can Hide Train-Car Subsystems

**Context:** User query "train car 138 propulsion" failed asset resolution even though `TC-138-PROP` exists, and follow-up WO queries incorrectly said no results.

**Root Cause:** Filter extraction set `asset_type=train_car` from generic words ("train", "car"), which excluded subsystem assets (`type=propulsion`). QueryEngine also lacked `TC-*`/train-car phrase ID extraction and WO search only re-injected strict `XXX-YY-NNN` IDs.

**Solution:**
- Added train-car ID normalization/extraction (`train car 138` and `TC 138`) with subsystem suffix derivation (`PROP`, `VOBC`, `D1..D4`).
- Added asset-type specificity ranking so subsystem types outrank generic `train_car` when both are present.
- Allowed WO search token reinjection for all extracted non-WO IDs (including `TC-*`).
- Added relaxed filter fallback for asset search and prompt guardrails to avoid claiming on-screen cards when result sets are empty.

**Rule:** In hierarchical asset domains (vehicle -> subsystem), never let generic entity terms ("train car") hard-filter out subsystem queries ("propulsion", "VOBC", "door"). Resolve candidate IDs first, then filter.

## 2026-03-04 - ID Regex Must Validate Prefix Whitelists to Avoid False Positives

**Context:** Query "open work orders for tc-138-prop" briefly produced extracted ID `FOR-TC-138`.

**Root Cause:** The generic `([A-Z]{2,3})-([A-Z]{2})-(\d+)` asset regex matched across natural-language tokens (`for tc 138`) without checking whether the prefix was a valid asset namespace.

**Solution:** Applied prefix whitelist validation using known asset prefixes before accepting normalized IDs.

**Rule:** Any broad ID regex used on natural-language text must validate matched prefixes against known namespaces; otherwise prepositions/stopwords can be misread as IDs.

## 2026-03-04 - Side-Channel Cards Must Cover Work-Order and Zero-Result Search Shapes

**Context:** User saw agent language implying data was available on screen, but no visible card appeared.

**Root Cause:** `_extract_media_cards` only supported asset/KB/report payloads. Smart-search work-order payloads and zero-result responses produced no UI card at all.

**Solution:** Added extraction rules for:
- Work-order payloads (`wo_id`, `asset_id`, `description`) -> work-order media cards
- Smart-search zero-result payloads (`intent`, `total=0`, `results=[]`) -> explicit "No Matching Records" card

**Rule:** Any tool-result side channel used as user-facing evidence must include both positive-result and empty-result shapes for the major entities; otherwise users see silent blanks and lose trust.
