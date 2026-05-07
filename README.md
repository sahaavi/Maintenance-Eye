# Maintenance-Eye

**Real-time AI Co-Pilot for Physical Infrastructure Maintenance**

Point your phone camera at equipment. Speak naturally. Your AI co-pilot sees, diagnoses, and acts.

[![Built with Google ADK](https://img.shields.io/badge/Google_ADK-Agent_Framework-4285F4?logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![Gemini 2.5 Flash](https://img.shields.io/badge/Gemini_2.5_Flash-Live_API-EA4335?logo=google&logoColor=white)](https://ai.google.dev/)
[![Deployed on Cloud Run](https://img.shields.io/badge/Cloud_Run-Deployed-0F9D58?logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Tests](https://img.shields.io/badge/Tests-140_collected-blue)](tests/)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform&logoColor=white)](terraform/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Category**: Live Agents -- Real-time audio + vision with barge-in interruption
>
> **Built for the** [Google Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/)

[Live Demo](https://maintenance-eye-swrz6daraq-uc.a.run.app)

---

## The Problem

Transit infrastructure maintenance -- escalators, switch machines, power transformers -- is high-stakes manual work. Technicians operate in noisy, hazardous environments with their hands occupied by tools and safety equipment.

The current workflow forces a painful cycle: **inspect visually, stop working, pull out a tablet, type findings into an Enterprise Asset Management (EAM) system, then resume work**. This "stop and type" friction leads to missed defects, incomplete maintenance records, and shortcuts on safety protocols.

EAM systems are powerful, but they demand focused data entry -- fundamentally incompatible with active fieldwork. Maintenance teams need an interface that works *with* them, not against them.

---

## The Solution

Maintenance-Eye replaces the "stop and type" cycle with a hands-free AI co-pilot that sees, listens, speaks, and acts in real time.

### Real-Time Visual Inspection

The AI sees through the phone camera at 2 FPS, identifying faults like corrosion, wear, cracks, leaks, and misalignment. Every finding gets a severity rating (P1 Critical through P5 Planned) with confidence scores and automatic EAM code classification (Problem Code / Fault Code / Action Code).

### Natural Voice Interaction with Barge-In

Bidirectional PCM audio streaming (16kHz in, 24kHz out) enables fully hands-free operation. Technicians speak naturally while working -- no "press to talk" button. Full barge-in interruption support means you can cut in mid-sentence and the agent stops immediately to listen.

### Agent Persona: "Max"

Max is a 20-year senior maintenance engineer -- professional, calm, safety-conscious, and concise. He speaks like a trusted colleague, not a chatbot. Field responses stay to 2-3 sentences because technicians are working, not reading.

### Human-in-the-Loop Safety

Critical actions go through a backend-enforced confirmation workflow: the agent proposes an action, the technician confirms, rejects, or corrects it via a visual card, and confirmed actions execute through deterministic backend code with required-field validation. The AI cannot create a work order, escalate a priority, or close a ticket directly; those mutations require explicit human approval.

### ASR-Aware Intelligent Search

Speech-to-text splits equipment IDs unpredictably -- "ESC-SC-003" becomes "e s c s c zero zero three." The QueryEngine NLP layer normalizes ASR-transcribed IDs, expands domain synonyms ("vibration" also searches "noise," "shaking"), and resolves fuzzy matches. This makes voice-driven equipment lookup reliable in noisy field environments.

### Enterprise Dashboard

A 5-page data explorer provides visibility into maintenance operations: Work Orders, Assets, Locations, Knowledge Base, and EAM Codes. Work Orders, Assets, Knowledge Base, and EAM Codes support search and filtering; Locations provides a grouped station overview. The layout is responsive, with sidebar navigation on desktop and bottom navigation on mobile.

---

## Architecture

![Maintenance-Eye Architecture](docs/architecture.png)

The Phone PWA captures camera frames (2 FPS JPEG) and microphone audio (PCM 16kHz), streaming them via WebSocket to the FastAPI backend on Cloud Run. The ADK Runner forwards media to the Gemini 2.5 Flash Live API for real-time multimodal reasoning. The agent invokes 9 specialized tools to query the active EAM backend, manage work orders, and enforce safety protocols. Responses stream back as PCM 24kHz audio, text transcripts, media cards, and confirmation cards.

---

## Agent Tools

The agent has 9 specialized tools -- this is not a wrapper around a single API call:

| Tool | Purpose | Example |
|------|---------|---------|
| `smart_search` | NLP-powered search across all entities with ASR normalization | "pump vibration", "wo 10234", "P1 open rolling stock" |
| `lookup_asset` | Retrieve full asset details by exact ID | "Look up ESC-SC-003" |
| `get_inspection_history` | Past inspections and recurring failure patterns | "Show me last 3 inspections for this escalator" |
| `search_knowledge_base` | Repair procedures, manuals, troubleshooting guides | "Escalator step chain lubrication procedure" |
| `manage_work_order` | Create, update, close, and search work orders | "Create P2 work order for handrail wear" |
| `get_safety_protocol` | PPE requirements, LOTO procedures, hazard warnings | "Safety protocol for high-voltage cabinet" |
| `generate_report` | Inspection reports with findings, open work orders, and recommendations | "Generate end-of-shift report" |
| `propose_action` | Human-in-the-loop confirmation for critical actions | Renders confirmation card in UI |
| `check_pending_actions` | View unconfirmed proposals awaiting decision | "Any pending confirmations?" |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| AI Model | Gemini 2.5 Flash (Live API) -- native audio model |
| Agent Framework | Google ADK (Agent Development Kit) v1.10 |
| Backend | Python 3.12 + FastAPI (fully async) |
| Frontend | Vanilla HTML/CSS/JS Progressive Web App |
| Database | Google Cloud Firestore with JSON-backed local/demo fallback |
| Storage | Google Cloud Storage for best-effort frame snapshots, report JSON, and work-order artifacts |
| Hosting | Google Cloud Run (0-3 autoscaling instances) |
| CI/CD | GitHub Actions test workflow + Cloud Build deployment config |
| IaC | Terraform |
| Containerization | Docker (multi-stage build, Python 3.12-slim) |

---

## Try It

### Option 1: Live Demo (Recommended)

Open the live deployment on your phone:

1. Navigate to **https://maintenance-eye-swrz6daraq-uc.a.run.app**
2. Tap **Start Inspection**
3. Choose an inspection asset
4. Allow camera and microphone access
5. Point your camera at equipment or a photo of equipment on another screen
6. Speak: *"What do you see? Are there any issues?"*
7. Try: *"Create a work order for this"* -- you will see a confirmation card appear
8. Try interrupting Max mid-sentence to test barge-in

### Option 2: Explore the Dashboard

1. Open the same URL on a desktop browser
2. Tap **Browse Data** on the home screen
3. Browse the 5 data pages: Work Orders, Assets, Locations, Knowledge Base, EAM Codes
4. Try searching: *"pump vibration"* or filter by priority *P1*

### Option 3: Verify Cloud Deployment

```bash
# Health check
curl https://maintenance-eye-swrz6daraq-uc.a.run.app/health

# Readiness check (validates the active EAM backend; check eam_backend)
curl https://maintenance-eye-swrz6daraq-uc.a.run.app/readiness

# Search assets via REST API
curl "https://maintenance-eye-swrz6daraq-uc.a.run.app/api/assets?q=escalator"

# Filter work orders
curl "https://maintenance-eye-swrz6daraq-uc.a.run.app/api/work-orders?status=open&priority=P1"
```

### What to Look For

- Real-time camera feed with scanning HUD overlay
- Natural voice responses from Max (native audio, not robotic TTS)
- Confirmation cards for critical actions (human-in-the-loop)
- Barge-in: interrupt Max mid-sentence and he stops immediately
- ASR intelligence: say equipment IDs naturally ("wo ten two three four") and Max resolves them

The hosted URL is a public unauthenticated demo using synthetic data. It is suitable for trying the workflow, not as a production-secured deployment.

---

## Quick Start

### Prerequisites

- Python 3.12+
- Google Cloud SDK ([install](https://cloud.google.com/sdk/docs/install))
- A GCP project with billing enabled
- Gemini API key from [AI Studio](https://aistudio.google.com/apikey)

### 1. Clone and configure

```bash
git clone https://github.com/sahaavi/Maintenance-Eye.git
cd Maintenance-Eye
cp .env.example .env
# Edit .env with your GCP project ID and Gemini API key
```

### 2. Install runtime dependencies

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run locally

The backend automatically falls back to a JSON-based EAM service when Firestore is unavailable -- no cloud setup needed for local testing:

```bash
python3 main.py
# Open http://localhost:8080 on your phone (same network)
```

### 4. (Optional) Run with Firestore emulator

```bash
firebase emulators:start          # Firestore @ localhost:8081
FIRESTORE_EMULATOR_HOST=localhost:8081 python3 main.py
```

### 5. Seed synthetic data

```bash
python3 ../scripts/seed_data.py
```

### 6. Run tests

From the repository root, install the development dependencies and run the test layer you need:

```bash
./scripts/setup_test_env.sh
source .venv/bin/activate
python -m pytest tests/unit -o "addopts=" -v   # 92 unit tests
```

For the full local quality gate, run `TEST_ENV=dev ./scripts/run_test_suite.sh`.

---

## Deploy to Google Cloud

### One-command deployment

```bash
./scripts/deploy.sh <project-id> <gemini-api-key> [region] [allowed-origins]
```

This script enables required GCP APIs, creates or updates the Artifact Registry repository and Gemini Secret Manager secret, builds the container with Cloud Build, and deploys Cloud Run. If Terraform is installed, it also provisions Firestore, the GCS bucket, Secret Manager resources, Artifact Registry, and Cloud Run from `terraform/`. Without Terraform, Firestore database and GCS bucket creation are not handled by the script.

Firestore auto-seeding runs during application startup when the active backend is `FirestoreEAM` and the Firestore `assets` collection is empty. `/readiness` validates the active EAM backend; check that `eam_backend` is `FirestoreEAM` when you need to confirm Cloud Firestore is in use.

The provided deployment path is public demo mode by default (`ENABLE_AUTH=false`, unauthenticated Cloud Run invoker). For production, enable Firebase Auth, restrict CORS, configure an explicit Cloud Run service account, grant least-privilege Firestore/Secret Manager/Storage IAM roles, and protect Terraform state because deployment handles secret material.

### Manual Terraform deployment

Manual Terraform deployment assumes the backend image already exists at
`<region>-docker.pkg.dev/<project-id>/maintenance-eye/backend:latest`. For first-time
deployments, the `deploy.sh` path is the safer route because it creates the image before
Terraform points Cloud Run at it.

```bash
cd terraform
terraform init
terraform apply \
  -var="project_id=YOUR_PROJECT" \
  -var="gemini_api_key=YOUR_KEY" \
  -var="region=us-central1"
```

---

## Project Structure

```
Maintenance-Eye/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment configuration
│   ├── api/
│   │   ├── routes.py              # REST endpoints
│   │   ├── websocket.py           # WebSocket handler (Live + Chat modes)
│   │   └── websocket_helpers.py   # Confirmation & media card helpers
│   ├── agent/
│   │   ├── maintenance_agent.py   # ADK agent definition
│   │   ├── prompts.py             # System prompts & Max persona
│   │   └── tools/                 # 9 ADK tool functions
│   ├── middleware/
│   │   └── security.py            # Security headers middleware
│   ├── services/
│   │   ├── eam_interface.py       # Abstract EAM service interface
│   │   ├── base_eam.py            # Shared search helpers
│   │   ├── json_eam.py            # JSON file fallback (local dev)
│   │   ├── firestore_eam.py       # Cloud Firestore implementation
│   │   ├── query_engine.py        # NLP pre-query intelligence layer
│   │   ├── search_matcher.py      # Token-aware text matching
│   │   ├── confirmation_manager.py # Human-in-the-loop action tracking
│   │   └── seeder.py              # Firestore data seeder
│   └── models/
│       └── schemas.py             # Pydantic data models
├── frontend/
│   ├── index.html                 # PWA entry (home, inspection, dashboard, chat panel)
│   ├── style.css                  # Core PWA styles
│   ├── command-center.css         # Dashboard, asset picker, confirmation editor styles
│   ├── app.js                     # Client: WebSocket, camera, mic, audio playback, UI
│   ├── command-center.js          # Dashboard summary, asset picker, confirmation editor
│   ├── sw.js                      # Service worker (static asset caching)
│   └── manifest.json              # PWA manifest
├── tests/                         # Unit, integration, API, system, security, AI, data, performance & E2E tests
├── data/                          # Seed data (125 assets, 146 WOs, 85 EAM codes)
├── terraform/                     # Infrastructure as Code (Cloud Run + IAM)
├── scripts/                       # Deployment, seeding & test scripts
├── docs/                          # Architecture diagram
├── .github/workflows/             # CI pipeline (lint, security, tests)
├── Dockerfile                     # Multi-stage container build
├── cloudbuild.yaml                # Cloud Build build/deploy config
└── .env.example                   # Environment variable template
```

---

## Google Cloud Services

| Service | Role |
|---------|------|
| **Gemini 2.5 Flash** (Live API) | Real-time multimodal AI with native audio -- the agent's brain |
| **Google ADK** | Agent framework with tool orchestration, session management, LiveRequestQueue |
| **Cloud Run** | Serverless container hosting with autoscaling (0-3 instances). The Cloud Build deploy path enables session affinity. |
| **Cloud Firestore** | NoSQL database for assets, work orders, inspections, EAM codes, and knowledge base; local/demo fallback uses JSON seed data |
| **Cloud Storage** | Best-effort audit artifacts: periodic frame snapshots, confirmed work-order JSON, and generated report JSON |
| **Cloud Build** | Builds and deploys the container when invoked manually or by an externally configured trigger |
| **Artifact Registry** | Docker image repository |
| **Secret Manager** | Runtime API key source for Cloud Run; protect deployment inputs and Terraform state |

---

## How I Built It

### The Bidirectional Streaming Core

The heart of Maintenance-Eye is a persistent WebSocket connection handling audio, video, and tool calls simultaneously. The ADK Runner with `LiveRequestQueue` bridges the mobile PWA to the Gemini Live API. Upstream: PCM 16kHz audio and JPEG frames stream into the ADK. Downstream: PCM 24kHz audio, text transcripts, rich media cards, and confirmation cards stream back to the technician.

### The ASR Challenge (Key Innovation)

Speech-to-text splits equipment IDs unpredictably -- "ESC-SC-003" becomes "e s c s c zero zero three." I built a QueryEngine NLP layer that normalizes ASR-transcribed IDs, expands domain synonyms, and resolves fuzzy matches against the EAM database. A companion `SearchMatcher` handles token-aware text matching with ASR domain corrections, making voice-driven equipment lookup reliable in noisy field environments.

### Human-in-the-Loop Safety (Key Design Decision)

Safety-critical work order creation requires multi-layered validation. The proposal tool requires core fields before a confirmation card can be rendered, the UI lets the technician confirm/reject/correct the proposal, and the backend executes confirmed mutations through a confirmation-only code path. This design was modeled after real SkyTrain maintenance operations across 6 departments with P1-P5 priority classification.

### What I Learned

- Native audio models need specific PCM sample rate matching (16kHz input, 24kHz output) -- mismatches produce silence or garbled audio
- ADK `send_realtime(blob)` takes a single positional argument, not a keyword argument -- subtle API detail that caused debugging time
- Firestore emulator is essential for rapid iteration without cloud costs
- A static vanilla JS PWA avoids build-step complexity while delivering camera, microphone, chat, dashboard, and service-worker shell caching

---

## Domain Context

Modeled after SkyTrain maintenance operations with 6 departments: Rolling Stock, Guideway, Power, Signal & Telecom, Facilities, and Elevating Devices. The EAM data model follows industry-standard classification: Problem Code, Fault Code, and Action Code. Priorities range from P1 (critical safety) through P5 (planned maintenance). The seed dataset includes 125 assets, 146 work orders, 85 EAM codes, 45 inspection records, and 27 knowledge base entries.

---

## What's Next

- **Production EAM integration**: The abstract `EAMService` interface is designed for plug-in backends -- Hexagon EAM, SAP PM, and Maximo are next
- **Multi-language support**: Diverse maintenance teams need inspection in their working language
- **Offline-first PWA**: Underground tunnels and remote substations have no connectivity -- queue inspections for sync
- **Multi-agent architecture**: Specialized sub-agents for electrical, mechanical, and structural domains
- **Predictive analytics**: Identify failure trends from historical inspection patterns before equipment breaks

---

## License

MIT License -- See [LICENSE](LICENSE)

Copyright (c) 2026 Avishek Saha
