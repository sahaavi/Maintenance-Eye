# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maintenance-Eye is an AI co-pilot for physical infrastructure maintenance, built for the Google Gemini Live Agent Challenge hackathon. Field technicians point their phone camera at equipment, speak naturally, and an ADK agent (persona: "Max") identifies faults via live video, auto-classifies using EAM codes, creates work orders with human-in-the-loop confirmation, and generates inspection reports.

**Category**: Live Agents (real-time audio+vision with barge-in interruption)

## Working with This Project

This project follows the workflow principles defined in `RULES.md`. 

## Development Commands

```bash
# Backend setup
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run backend (serves frontend static files too)
python main.py                    # http://localhost:8080

# Run with Firestore emulator (local dev)
firebase emulators:start          # Firestore @ localhost:8081
FIRESTORE_EMULATOR_HOST=localhost:8081 python main.py

# Seed synthetic data to Firestore
./scripts/setup_and_seed.sh
python scripts/seed_data.py

# Deploy to GCP
./scripts/deploy.sh <project-id> <gemini-api-key> [region]
```

No test suite or linter is currently configured.

## Bug Reporting & Maintenance

To maintain a consistent `BUG_REPORT.md` across all AI agents (Claude, Gemini, etc.), use the provided management script:

```bash
# Add a new bug
python scripts/manage_bugs.py add "Bug Description" --severity critical --component "Backend" --impact "Crashes on startup"

# Update bug status
python scripts/manage_bugs.py update C-001 --status "Fixed"
```

AI agents should run this script whenever they identify a new bug or resolve an existing one.

## Architecture

```
Phone PWA ──WebSocket──▶ FastAPI ──ADK Runner──▶ Gemini 2.5 Flash (Live API)
  (camera+mic)           │                          │
                         │                     8 ADK Tools
                         ▼                          │
                    REST API ◀──────────────────────▼
                         │                    Firestore (EAM data)
                    Confirmation              Cloud Storage (photos)
                    Manager
```

**Backend** (`backend/`): Python 3.12 + FastAPI + Google ADK. Fully async.
- `main.py` — FastAPI app, ADK Runner init with `InMemorySessionService`, static file serving
- `agent/maintenance_agent.py` — ADK Agent definition (model: `gemini-live-2.5-flash-native-audio`)
- `agent/prompts.py` — System prompt defining "Max" persona, severity ratings, EAM code classification
- `agent/tools/` — 8 tool functions (asset lookup, work orders, safety, reports, human-in-the-loop confirmation)
- `api/websocket.py` — Bidirectional WebSocket handler using ADK `LiveRequestQueue` for audio/video/text streaming
- `api/routes.py` — REST endpoints for assets, work orders, inspections, knowledge base, confirmation flow, reports
- `services/eam_interface.py` — Abstract EAM service (pluggable: Firestore for hackathon, Hexagon EAM for production)
- `services/firestore_eam.py` — Firestore async implementation
- `services/confirmation_manager.py` — Human-in-the-loop action tracking (propose → confirm/reject/correct)
- `models/schemas.py` — Pydantic models (Asset, WorkOrder, EAMCode, InspectionRecord, etc.)

**Frontend** (`frontend/`): Vanilla HTML/CSS/JS PWA. No build step.
- `app.js` — Single-file client: WebSocket streaming, camera capture (2 FPS JPEG), mic capture (PCM 16kHz), audio playback (PCM 24kHz), confirmation card UI, 5-page data explorer with debounced search + filter dropdowns
- `index.html` — Three screens: splash, inspection (camera+agent), dashboard (5-page enterprise explorer: Work Orders, Assets, Locations, Knowledge Base, EAM Codes)
- `style.css` — Enterprise dashboard styles: sidebar nav (desktop), bottom nav (mobile), filter bars, data tables, status/priority badges

**Infrastructure**: Docker (Python 3.12-slim), Cloud Run (0-3 instances), Terraform, Cloud Build CI/CD.

## Key Design Patterns

- **Human-in-the-loop**: Agent proposes critical actions via `propose_action()` → technician confirms/rejects/corrects via WebSocket → only then executes `manage_work_order()`
- **Firestore fallback**: REST routes AND agent tools fall back to `JsonEAM` (backed by `data/seed_data.json`) if Firestore is unavailable; `get_eam_service()` singleton handles this transparently
- **EAM abstraction**: `EAMService` interface allows swapping database backends without changing agent tools
- **Audio streaming**: Client sends PCM 16kHz, receives PCM 24kHz; bidirectional via WebSocket with ADK LiveRequestQueue
- **Session management**: In-memory only (stateless Cloud Run), per-session confirmation manager

## Domain Context

Modeled after SkyTrain maintenance operations with 6 departments (Rolling Stock, Guideway, Power, Signal & Telecom, Facilities, Elevating Devices). EAM codes follow Problem Code → Fault Code → Action Code classification. Priorities are P1 (critical/safety) through P5 (planned).

## Configuration

Environment variables loaded from `.env` via `backend/config.py`:
- `GCP_PROJECT_ID`, `GEMINI_API_KEY`, `FIRESTORE_DATABASE`, `GCS_BUCKET`
- `FIRESTORE_EMULATOR_HOST` — set for local dev with emulator
- `APP_PORT` (default 8080), `APP_ENV`, `LOG_LEVEL`
