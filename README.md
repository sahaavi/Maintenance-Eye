# Maintenance-Eye 🔍

> **AI Co-Pilot for Physical Infrastructure Maintenance Operations**

Built for the [Google Gemini Live Agent Challenge](https://devpost.com/) hackathon.

## What It Does

Maintenance-Eye is a **real-time AI-powered visual inspection agent** for field maintenance technicians. Point your phone camera at equipment, talk naturally, and the agent:

- 🎥 **Sees** equipment conditions via live camera feed
- 🔍 **Identifies** faults, wear, corrosion, and anomalies in real-time
- 🗣️ **Speaks** findings with severity ratings and confidence scores
- 🏷️ **Auto-classifies** using EAM codes (Problem / Fault / Action)
- 📋 **Creates work orders** with technician confirmation (human-in-the-loop)
- 📊 **Generates inspection reports** with photos and recommendations
- ⚡ Supports **natural voice interruptions** (barge-in)
- 🛡️ **Safety-first** — always verifies LOTO/PPE before inspection

## Architecture

```
📱 Phone PWA (Camera + Mic + GPS)
       ↕ WebSocket
⚡ Cloud Run Backend (FastAPI)
       ↕
🤖 Google ADK Agent ("Max")
   ├── 🔎 smart_search
   ├── 🔧 lookup_asset
   ├── 📜 get_inspection_history
   ├── 📚 search_knowledge_base
   ├── 📝 manage_work_order
   ├── ⚠️ get_safety_protocol
   ├── 📊 generate_report
   ├── ✅ propose_action
   └── 📋 check_pending_actions
       ↕
🧠 Gemini 2.5 Flash (Live API)
       ↕
🗄️ Firestore + Cloud Storage
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML/JS Progressive Web App |
| Backend | Python + FastAPI |
| AI Model | Gemini 2.5 Flash via Live API |
| Agent Framework | Google ADK (Agent Development Kit) |
| Database | Google Cloud Firestore |
| Storage | Google Cloud Storage |
| Hosting | Google Cloud Run |
| IaC | Terraform |

## Quick Start

### Prerequisites

- Python 3.12+
- Google Cloud SDK (`gcloud`)
- A GCP project with billing enabled
- Gemini API key

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/Maintenance-Eye.git
cd Maintenance-Eye
touch .env
# Edit .env with your GCP project ID and Gemini API key
```

### 2. Install dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Seed synthetic data

```bash
python ../scripts/seed_data.py
```

### 4. Run locally

```bash
python main.py
```

Open `http://localhost:8080` on your phone (same network) to start inspecting.

### 5. Deploy to Google Cloud

```bash
# Using Terraform (recommended)
cd terraform
terraform init
terraform apply -var="project_id=YOUR_PROJECT" -var="gemini_api_key=YOUR_KEY"

# Or using the deploy script
bash scripts/deploy.sh
```

## Project Structure

```
Maintenance-Eye/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py             # Environment configuration
│   ├── api/
│   │   ├── routes.py         # REST endpoints
│   │   ├── websocket.py      # WebSocket handler (Live + Chat)
│   │   └── websocket_helpers.py  # Confirmation & media card helpers
│   ├── agent/
│   │   ├── maintenance_agent.py  # ADK agent definition
│   │   ├── prompts.py        # System prompts & persona
│   │   └── tools/            # 9 ADK tool functions
│   ├── services/
│   │   ├── eam_interface.py  # Abstract EAM service
│   │   ├── base_eam.py       # Shared search helpers
│   │   ├── json_eam.py       # JSON file fallback
│   │   ├── firestore_eam.py  # Firestore implementation
│   │   ├── query_engine.py   # NLP pre-query intelligence
│   │   ├── search_matcher.py # Token-aware text matching
│   │   └── seeder.py         # Firestore data seeder
│   └── models/
│       └── schemas.py        # Pydantic data models
├── frontend/
│   ├── index.html            # PWA entry
│   ├── style.css             # Dark theme UI
│   ├── app.js                # Client application
│   └── manifest.json         # PWA manifest
├── tests/                    # Unit, integration & E2E tests
├── data/                     # Seed data (JSON)
├── terraform/                # Infrastructure as Code
├── scripts/                  # Deployment & data scripts
├── demo/                     # Demo script & video analysis
├── hackathon/                # Challenge rules
└── Dockerfile                # Container build
```

## Category

**Live Agents** — Real-time audio/vision interaction with interruption handling.

## Google Cloud Services Used

- **Cloud Run** — Hosts the backend
- **Firestore** — Stores assets, work orders, inspection records
- **Cloud Storage** — Stores inspection photos and reports
- **Gemini 2.5 Flash** (Live API) — Real-time multimodal AI
- **Cloud Build** + **Artifact Registry** — CI/CD pipeline

## How We Built It

Built with **Google ADK** (Agent Development Kit) and the **Gemini 2.5 Flash Live API** for real-time multimodal interaction. The agent ("Max") processes live camera frames at 2 FPS and bidirectional audio (PCM 16kHz in, 24kHz out) over WebSocket, enabling hands-free inspection while technicians work.

**Key challenge:** Speech-to-text splits equipment IDs unpredictably ("ESC-SC-003" becomes "e s c s c zero zero three"). We built a QueryEngine NLP layer that normalizes ASR-transcribed IDs, expands domain synonyms, and resolves fuzzy matches — making voice-driven equipment lookup reliable in noisy field environments.

**Key learning:** Safety-critical work order creation requires multi-layered validation. We enforce required fields at three independent checkpoints: proposal, tool execution, and post-confirmation automation — so no layer can be bypassed.

**What's next:** Integration with production EAM systems (Hexagon, SAP PM), multi-language support for diverse maintenance teams, and offline-first PWA capabilities for underground or remote inspection sites.

## License

MIT License — See [LICENSE](LICENSE)
