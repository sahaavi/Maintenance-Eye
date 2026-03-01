## Workflow Orchestration for Maintenance-Eye

### 1. Plan Node Strategy
Enter plan mode for:
- **ANY ADK agent changes** (tools, prompts, confirmation flows)
- **WebSocket protocol modifications** (audio/video streaming, message formats)
- **EAM interface changes** (affects both Firestore and future Hexagon integration)
- **Safety-critical features** (work order creation, severity classification, P1 incidents)
- **Multi-component flows** (camera → WebSocket → ADK → Firestore → confirmation → response)

**Stop and re-plan if:**
- WebSocket connection drops unexpectedly during testing
- ADK Live API responses don't match expected schema
- Confirmation flow state machine gets confused
- Audio playback breaks or introduces latency spikes

**Always verify before implementation:**
````bash
# Backend readiness
firebase emulators:start
FIRESTORE_EMULATOR_HOST=localhost:8081 python main.py

# Frontend testing checklist
□ Camera capture @ 2 FPS works on mobile
□ Microphone streams PCM 16kHz without clipping
□ Audio playback is smooth (PCM 24kHz)
□ Confirmation cards render and respond correctly
````

### 2. Subagent Strategy for This Project

**Offload to subagents:**
- Researching Gemini Live API edge cases (barge-in, session limits, streaming errors)
- Exploring ADK tool patterns from documentation
- Analyzing Firestore query performance for large asset datasets
- Testing audio codec compatibility across browsers
- Investigating WebSocket reconnection strategies

**Keep in main context:**
- Core agent logic (`maintenance_agent.py`, `prompts.py`)
- WebSocket streaming implementation (`websocket.py`)
- Human-in-the-loop confirmation manager state machine
- Critical path debugging (P1 incidents, data loss scenarios)

**Parallel analysis pattern:**
````
Subagent 1: Research ADK streaming best practices
Subagent 2: Test audio encoding on Safari vs Chrome
Subagent 3: Analyze EAM code classification accuracy
Main: Integrate findings and implement
````

### 3. Self-Improvement Loop (Domain-Specific)

After user corrections, update `tasks/lessons.md` with:

**ADK/Gemini Patterns:**
- "Always validate tool response schemas before returning to agent"
- "Test barge-in interruption with long agent responses"
- "Never assume Live API session persists beyond WebSocket disconnect"

**Audio/Video Streaming:**
- "Capture JPEG quality vs bandwidth tradeoff at 2 FPS"
- "PCM buffer size must match sample rate exactly (16kHz = 16000 samples/sec)"
- "Audio desync = check clock drift between client and server"

**Safety-Critical Domain:**
- "P1 incidents require human confirmation BEFORE creating work order"
- "EAM code fallback: always show 'Unknown' vs silently failing"
- "Photo evidence is mandatory for structural/electrical faults"

**Session Start Ritual:**
````bash
# Review lessons relevant to today's work
grep -i "websocket\|audio\|adk" tasks/lessons.md
````

### 4. Verification Before Done (Safety-Critical System)

**Never mark complete without:**

1. **End-to-End Flow Test:**
````bash
   # Start backend + emulator
   firebase emulators:start &
   FIRESTORE_EMULATOR_HOST=localhost:8081 python main.py
   
   # Test critical path
   □ Open PWA on mobile device (not just desktop Chrome)
   □ Point camera at test equipment
   □ Speak fault description
   □ Verify agent response via audio playback
   □ Confirm proposed action in UI
   □ Check work order created in Firestore emulator
   □ Validate inspection report generated
````

2. **Data Integrity Checks:**
````python
   # Verify Firestore writes
   □ Work order has all required fields (asset_id, severity, eam_codes)
   □ Inspection record links to photo in GCS
   □ Confirmation log shows technician decision
   □ Timestamps are ISO 8601 compliant
````

3. **Audio/Video Quality:**
````bash
   # Check WebSocket logs
   □ No dropped frames during 30-second test
   □ Audio latency < 500ms (record → playback)
   □ Video frame rate stable at ~2 FPS
   □ No memory leaks after 5-minute session
````

4. **ADK Agent Behavior:**
````bash
   # Test Max persona consistency
   □ Uses safety-conscious language for P1/P2 incidents
   □ Asks clarifying questions before classifying faults
   □ Proposes actions via confirmation flow (not auto-execute)
   □ Handles interruptions gracefully (barge-in works)
````

5. **Diff Review Questions:**
   - "Would a SkyTrain maintenance supervisor trust this?"
   - "Can this fail silently and create a safety hazard?"
   - "Does this break Firestore → Hexagon EAM migration path?"
   - "Will this work on a technician's phone in a noisy train yard?"

### 5. Demand Elegance (Balanced for Real-Time Systems)

**Pause and ask "is there a more elegant way?" for:**
- State management in confirmation flow (currently in-memory dict)
- EAM code classification logic (rule-based vs ML-assisted)
- WebSocket message routing (type-based dispatch)
- Audio buffer handling (circular buffer vs queue)

**Skip optimization for:**
- Simple CRUD endpoints (`/api/assets`, `/api/work-orders`)
- One-off seed data scripts
- Deployment scripts (functional > elegant)
- MVP-phase frontend code (vanilla JS is fine for hackathon)

**Red flags that demand rethinking:**
- Nested try/except blocks in WebSocket handler
- Manual JSON serialization instead of Pydantic
- Hardcoded EAM codes in tool functions
- Synchronous Firestore calls in async FastAPI routes
- Copy-pasted audio encoding logic

**The Elegance Test:**
````python
# Before (hacky)
if message["type"] == "audio":
    handle_audio(message["data"])
elif message["type"] == "video":
    handle_video(message["data"])
elif message["type"] == "text":
    handle_text(message["data"])
# ... 8 more elif blocks

# After (elegant)
HANDLERS = {
    "audio": handle_audio,
    "video": handle_video,
    "text": handle_text,
}
HANDLERS[message["type"]](message["data"])
````

### 6. Autonomous Bug Fixing (Real-Time System Debugging)

**When given a bug report, immediately:**

1. **Reproduce Locally:**
````bash
   # Check logs first
   tail -f backend/logs/app.log | grep ERROR
   
   # Start emulator if needed
   firebase emulators:start
   
   # Run backend with debug logging
   LOG_LEVEL=DEBUG python main.py
````

2. **Identify Root Cause Categories:**
   - **WebSocket disconnect** → Check `websocket.py` connection handling
   - **ADK tool failure** → Inspect tool response schema in `agent/tools/`
   - **Audio glitches** → Review PCM encoding in `app.js`
   - **Confirmation stuck** → Debug `ConfirmationManager` state machine
   - **Firestore timeout** → Verify emulator connection or indexes

3. **Fix Without Hand-Holding:**
````bash
   # User reports: "Agent doesn't respond to audio"
   
   # Don't ask "what browser?" or "can you share logs?"
   # Instead:
   
   # 1. Check WebSocket audio message handling
   grep -n "audio_chunk" backend/api/websocket.py
   
   # 2. Test ADK LiveRequestQueue integration
   python -c "from agent.maintenance_agent import agent; print(agent)"
   
   # 3. Verify audio encoding matches ADK spec (PCM 16kHz mono)
   # → Find mismatch in app.js (was sending 48kHz stereo)
   # → Fix and test
   
   # 4. Commit with clear message
   git commit -m "fix: correct audio encoding to PCM 16kHz mono for ADK Live API"
````

4. **Real-Time System Debug Checklist:**
````bash
   □ WebSocket connection established? (check Network tab)
   □ Audio chunks arriving at backend? (log message sizes)
   □ ADK Live API receiving audio? (check ADK Runner logs)
   □ Agent response generated? (inspect tool call results)
   □ Response sent back to client? (WebSocket send logs)
   □ Audio decoded and played? (browser console errors)
````

## Task Management (Maintenance-Eye Context)

### 1. Plan First
Write plan to `tasks/todo.md` with:
````markdown
## [Feature Name] - [Date]

**Scope:** 
- Component(s): backend/agent, frontend/app.js, infra
- Risk Level: Low/Medium/High (safety-critical flag)
- Dependencies: Firestore emulator, ADK credentials, test device

**Checklist:**
- [ ] Update ADK agent tool definition
- [ ] Modify WebSocket message handler
- [ ] Add Firestore schema migration
- [ ] Update frontend confirmation UI
- [ ] Test on mobile device (not just desktop)
- [ ] Verify end-to-end flow with audio/video
- [ ] Update CLAUDE.md if architecture changes
````

### 2. Verify Plan
Before implementing, confirm:
- Does this maintain EAM abstraction for future Hexagon migration?
- Will this work offline (PWA consideration)?
- Does this require new Firestore indexes?
- Any security implications (API keys, user data)?

### 3. Track Progress
Update `tasks/todo.md` in real-time:
````markdown
- [x] ~~Tool definition updated~~ (commit abc123)
- [🔄] WebSocket handler WIP - debugging audio decode issue
- [ ] Frontend UI pending backend completion
````

### 4. Explain Changes
High-level summary after each milestone:
````markdown
**Progress Update:**
Implemented `search_safety_procedures()` tool:
- Added to agent/tools/safety.py
- Integrated with Firestore safety_procedures collection
- Tested with "lockout/tagout" query → returns 3 relevant procedures
- Next: Add to frontend knowledge base display
````

### 5. Document Results
Add review section to `tasks/todo.md`:
````markdown
## Review - [Feature Name]

**What Worked:**
- ADK tool integration was straightforward
- Confirmation flow state machine handled edge cases well

**What Didn't:**
- Audio latency spiked on Safari (PCM decoding issue)
- Firestore composite index not auto-created (manual fix required)

**Production Readiness:**
- [ ] Load tested with 10 concurrent sessions
- [ ] Tested on iOS Safari + Android Chrome
- [ ] Error handling covers all tool failure modes
- [ ] Logging sufficient for debugging in Cloud Run
````

### 6. Capture Lessons
Update `tasks/lessons.md` after corrections:
````markdown
## 2025-02-28 - Audio Latency Investigation

**Problem:** Audio playback delayed by 2-3 seconds on Safari

**Root Cause:** Safari requires AudioContext to be created in user gesture handler

**Solution:**
```javascript
// Don't create AudioContext at module load
// Instead, create on first user interaction
document.addEventListener('click', () => {
  if (!audioContext) {
    audioContext = new AudioContext({ sampleRate: 24000 });
  }
}, { once: true });
```

**Rule:** Always defer AudioContext creation to user gesture for Safari compatibility
````

## Core Principles (Safety-Critical Context)

### Simplicity First
- **Every change as simple as possible:** Real-time audio/video is complex enough—keep everything else simple
- **Minimal code impact:** A change to WebSocket handler shouldn't touch EAM interface
- **Progressive enhancement:** Feature should degrade gracefully if WebSocket drops

### No Laziness (Infrastructure Domain)
- **Find root causes:** "Audio doesn't work" → debug PCM encoding, sample rates, buffer sizes, codec support
- **No temporary fixes:** This is safety-critical infrastructure—hacks create incidents
- **Senior developer standards:** Code review yourself through the lens of a staff engineer at Hexagon or Siemens

### Minimal Impact
- **Changes touch only what's necessary:** Don't refactor `eam_interface.py` while fixing audio bug
- **Avoid introducing bugs:** Test on actual mobile device, not just desktop Chrome DevTools
- **Backwards compatibility:** Keep REST API stable even as WebSocket protocol evolves

### Domain-Specific Principle: Safety First
- **P1 incidents cannot auto-execute:** Always require human confirmation
- **Photo evidence for structural faults:** Don't create work order without visual proof
- **Graceful degradation:** If ADK fails, fall back to manual work order form (future feature)
- **Audit trail:** Log every technician decision (confirm/reject/correct) to Firestore