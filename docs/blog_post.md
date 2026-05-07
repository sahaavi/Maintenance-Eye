# Building Maintenance-Eye: A Real-Time AI Co-Pilot for Infrastructure Maintenance with Gemini Live API and Google ADK

*I built this project and wrote this article for the purposes of entering the [Google Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/). #GeminiLiveAgentChallenge*

---

Imagine you're a maintenance technician standing in front of a corroded escalator motor in a busy transit station. Your hands are full — one holding a flashlight, the other gripping a safety railing. You can see the problem: corrosion on the drive chain, a worn step roller, oil pooling where it shouldn't be. But to do anything about it, you need to stop what you're doing, pull out a tablet, navigate to the Enterprise Asset Management (EAM) system, type in your findings, look up the right fault codes, and create a work order. Then put the tablet away and get back to actually working.

This "stop and type" cycle is the silent productivity killer in infrastructure maintenance. I built Maintenance-Eye to eliminate it.

---

## The Problem: When Software Fights the Worker

Transit infrastructure maintenance — escalators, switch machines, power transformers — is high-stakes manual work. Technicians operate in noisy, hazardous environments with their hands occupied by tools and safety equipment. EAM systems are powerful databases, but they demand focused data entry: keyboard input, dropdown menus, code lookups. That interface is fundamentally incompatible with active fieldwork.

The consequences are real. Missed defects because a technician didn't want to stop and document mid-inspection. Incomplete maintenance records because typing on a tablet in the rain isn't practical. Shortcuts on safety protocols because the paperwork takes longer than the repair.

What if the interface could work *with* the technician instead of against them? What if instead of stopping to type, they could just talk?

---

## The Solution: Meet Max

Maintenance-Eye is a hands-free AI co-pilot that sees, listens, speaks, and acts in real time. The technician opens a Progressive Web App on their phone, points the camera at equipment, and starts talking.

The AI agent — named "Max" — has the persona of a 20-year senior maintenance engineer. Professional, calm, safety-conscious, and concise. Max speaks like a trusted colleague, not a chatbot. Field responses stay to 2-3 sentences because technicians are working, not reading.

Here's what happens in a typical inspection:

1. The technician approaches an escalator and says: *"Max, I'm at the King George station escalator. Starting inspection."*
2. Max sees the camera feed and responds with a safety briefing: *"Copy that. Before we start — confirm LOTO is in place and you have your hard hat and safety glasses on."*
3. As the technician pans the camera across the equipment, Max identifies issues in real time: *"I'm seeing corrosion on the drive chain sprocket. Looks like moderate severity — I'd call that a P2. Want me to create a work order?"*
4. A confirmation card appears on screen. The technician taps "Confirm" and the work order is created — without ever putting down a tool.

The key innovation: **natural voice with full barge-in support**. The technician can interrupt Max mid-sentence, and he stops immediately to listen. No "press to talk" button. No waiting for the AI to finish. Just natural conversation while working.

---

## Architecture: Bidirectional Streaming at the Core

![Maintenance-Eye Architecture](architecture.png)

The architecture centers on a persistent bidirectional WebSocket connection that handles audio, video, and tool calls simultaneously. This isn't a request-response system — it's a continuous stream.

**Upstream** (technician to AI): The phone PWA captures camera frames at 2 FPS as JPEG images and microphone audio as PCM at 16kHz. Both streams flow through the WebSocket to a FastAPI backend running on Google Cloud Run.

**The brain**: The backend uses the Google Agent Development Kit (ADK) Runner with a `LiveRequestQueue` to forward media to the Gemini 2.5 Flash Live API. This is a native audio model — Max's voice is generated directly by the model, not synthesized by a separate TTS engine. The difference in naturalness is immediately noticeable.

**Downstream** (AI to technician): Responses stream back as PCM 24kHz audio, text transcripts, rich media cards (equipment details, inspection history), and confirmation cards (for human-in-the-loop actions). The technician hears Max speak while simultaneously seeing relevant data appear on screen.

The PCM sample rate mismatch (16kHz in, 24kHz out) was one of the trickiest implementation details — getting it wrong produces silence or garbled audio with no obvious error message.

---

## Key Innovation: ASR-Aware Intelligent Search

Speech-to-text is remarkably good at natural language but remarkably bad at equipment IDs. When a technician says "ESC-SC-003," the ASR transcription might produce "e s c s c zero zero three" or "esc sc 003" or a dozen other variations. Standard database lookups fail completely.

I built a QueryEngine NLP layer that sits between the agent and the database. It handles:

- **ID normalization**: Reconstructs equipment IDs from fragmented ASR output. "e s c s c zero zero three" becomes "ESC-SC-003."
- **Domain synonym expansion**: A search for "vibration" also checks "noise," "shaking," and "oscillation." "Pump" also searches "motor," "compressor."
- **Intent detection**: Distinguishes between "show me work order 10234" (specific lookup) and "any open P1 work orders for rolling stock?" (filtered search).
- **Fuzzy matching**: When exact matches fail, token-aware text matching with ASR domain corrections finds the right result.

This layer is what makes voice-driven equipment lookup reliable in noisy field environments — the core use case for a maintenance co-pilot.

---

## Human-in-the-Loop: The AI Never Acts Alone

For a maintenance system, reliability isn't optional. An AI that creates incorrect work orders or misclassifies fault codes erodes trust faster than it builds it. I implemented a 3-stage confirmation system:

**Layer 1 — Proposal**: When Max determines an action is needed (creating a work order, escalating a priority, closing a ticket), he calls the `propose_action` tool instead of executing directly. This generates a structured proposal with all required fields.

**Layer 2 — Confirmation**: The proposal renders as a visual confirmation card on the technician's screen with three options:
- **Confirm**: Proceed with the AI's recommendation as-is
- **Reject**: Cancel the action entirely
- **Correct**: Edit the priority, problem code, or description before executing

**Layer 3 — Backend execution**: After confirmation, the backend executes the mutation through a confirmation-only workflow with required-field validation and returns an execution result. This demo does not include a separate audit-grade read-after-write verification pass.

The principle: Max is a tool for the technician, not a replacement for their expertise. The AI recommends, the human decides.

---

## The Agent's Toolbox: 9 Specialized Tools

Maintenance-Eye is not a wrapper around a single API call. The ADK agent has 9 purpose-built tools, each handling a specific aspect of the maintenance workflow:

| Tool | Purpose |
|------|---------|
| `smart_search` | NLP-powered search across all entities with ASR normalization |
| `lookup_asset` | Retrieve full asset details, specifications, and maintenance history |
| `get_inspection_history` | Past inspections and recurring failure patterns for an asset |
| `search_knowledge_base` | Repair procedures, technical manuals, troubleshooting guides |
| `manage_work_order` | Create, update, close, and search work orders |
| `get_safety_protocol` | PPE requirements, LOTO procedures, hazard warnings |
| `generate_report` | Inspection reports with findings, open work orders, and recommendations |
| `propose_action` | Human-in-the-loop confirmation for critical actions |
| `check_pending_actions` | View unconfirmed proposals awaiting technician decision |

The agent is grounded in real data: 125 assets, 146 work orders, 85 EAM codes, 45 inspection records, and 27 knowledge base entries — modeled after real SkyTrain maintenance operations across 6 departments (Rolling Stock, Guideway, Power, Signal & Telecom, Facilities, and Elevating Devices).

---

## Built on Google Cloud

Every layer of Maintenance-Eye runs on Google Cloud services:

- **Gemini 2.5 Flash (Live API)** — The real-time multimodal AI engine. Native audio generation means Max sounds natural, not robotic. Processes camera frames and audio simultaneously for true "see and speak" capability.

- **Google ADK (Agent Development Kit)** — Agent orchestration framework. Handles tool binding, session management, and the `LiveRequestQueue` that bridges the WebSocket to the Gemini Live API. Version 1.10 with full barge-in interruption support.

- **Cloud Run** — Serverless container hosting with 0-3 autoscaling instances. The Cloud Build deployment path enables session affinity, and the backend scales to zero when idle, keeping costs minimal during development.

- **Cloud Firestore** — NoSQL database storing assets, work orders, inspection records, EAM codes, and knowledge base entries. When Firestore credentials are unavailable, the backend falls back to local JSON seed data for local/demo use; API and WebSocket interactions still require a reachable backend.

- **Cloud Storage** — Stores best-effort audit artifacts: periodic session frame snapshots, confirmed work-order JSON artifacts, and generated report JSON. PDF reports are rendered on demand from process-local report data.

- **Cloud Build** — Builds and deploys the container when invoked manually or by an externally configured trigger. GitHub Actions handles the committed test workflow.

- **Artifact Registry** — Docker image repository for versioned container builds.

- **Secret Manager** — Runtime source for API keys and credentials referenced by Cloud Run. The deployment path handles secret material, so Terraform state and command history need appropriate protection for production keys.

The demo infrastructure path is automated with Terraform and a one-command deployment script. By default it creates a public unauthenticated demo deployment; production use should enable Firebase Auth, restrict CORS, and apply least-privilege runtime IAM.

---

## What I Learned

**PCM sample rate precision matters**: The Gemini Live API expects 16kHz input and produces 24kHz output. Sending audio at the wrong sample rate produces silence or garbled speech with no error message. This took significant debugging time because the failure mode is silent.

**ADK API subtleties**: `send_realtime(blob)` takes a single positional argument, not a keyword argument. A small API detail that caused hours of debugging. The ADK documentation has improved significantly, but real-time streaming edge cases still require careful testing.

**The Firestore emulator is essential**: Rapid iteration on database queries without cloud costs or latency made development dramatically faster. I could test the full agent-to-database pipeline locally in seconds.

**Vanilla JS PWA was the right call**: No build step, no framework overhead. The frontend is a static PWA centered on `index.html`, `app.js`, `style.css`, `command-center.js`, `command-center.css`, `sw.js`, and `manifest.json`. It handles WebSocket streaming, camera capture at 2 FPS, microphone capture at 16kHz, audio playback at 24kHz, confirmation card UI, chat, and a full 5-page enterprise data explorer. Sometimes the simplest architecture is the most robust.

---

## What's Next

- **Production EAM integration**: The abstract `EAMService` interface is designed for plug-in backends — Hexagon EAM, SAP PM, and Maximo are the next targets.
- **Multi-language support**: Diverse maintenance teams need inspection in their working language.
- **Offline-first PWA**: Underground tunnels and remote substations have no connectivity — inspection data needs to queue for sync.
- **Predictive analytics**: Identify failure trends from historical inspection patterns before equipment breaks.

---

*Maintenance-Eye is open source. Check it out on [GitHub](https://github.com/sahaavi/Maintenance-Eye) or try the [live demo](https://maintenance-eye-swrz6daraq-uc.a.run.app).*

*I built this project and wrote this article for the purposes of entering the [Google Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/). #GeminiLiveAgentChallenge*
