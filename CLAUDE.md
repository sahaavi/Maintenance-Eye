# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maintenance-Eye is an AI co-pilot for physical infrastructure maintenance, built for the Google Gemini Live Agent Challenge hackathon. Field technicians point their phone camera at equipment, speak naturally, and an ADK agent (persona: "Max") identifies faults via live video, auto-classifies using EAM codes, creates work orders with human-in-the-loop confirmation, and generates inspection reports.

**Category**: Live Agents (real-time audio+vision with barge-in interruption)

## Working with This Project

This project follows the workflow principles defined in `RULES.md`.

## Mandatory RULES Workflow

Follow this sequence on every feature, fix, and refactor:

1. Read `RULES.md` before implementation if you have not read it in the current session.
2. Create or update a scoped plan in `tasks/todo.md` before writing code.
3. Update `tasks/todo.md` continuously while working (mark done items, add WIP notes, and record milestone summaries).
4. After each correction, failed assumption, or bug fix, append a lesson entry to `tasks/lessons.md` with context, root cause, solution, and a durable rule.
5. Run verification steps required by `RULES.md` before marking work complete, then log the review outcome in `tasks/todo.md`.
6. If architecture, workflow, or operating assumptions changed, reflect that change in this file and sibling agent guidance files.

Path convention:
- Canonical lessons log is `tasks/lessons.md` (plural).
- Do not use `tasks/lesson.md`.

## Development Commands

```bash
# Backend setup
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run backend (serves frontend static files too)
python3 main.py                   # http://localhost:8080

# Run with Firestore emulator (local dev)
firebase emulators:start          # Firestore @ localhost:8081
FIRESTORE_EMULATOR_HOST=localhost:8081 python3 main.py

# Seed synthetic data to Firestore
./scripts/setup_and_seed.sh
python3 scripts/seed_data.py

# Deploy to GCP
./scripts/deploy.sh <project-id> <gemini-api-key> [region]
```

## Test System Commands

```bash
# One-time test environment bootstrap
./scripts/setup_test_env.sh
source .venv/bin/activate

# Run full production test gate (env-aware)
TEST_ENV=dev ./scripts/run_test_suite.sh

# Run layered suites directly
python3 -m pytest -m "unit or integration or api"
python3 -m pytest -m "security or ai or data"
python3 -m pytest -m "performance"
python3 -m pytest -m "e2e"

# Run specific test files (bypasses global coverage gate)
python3 -m pytest -o "addopts=" tests/unit/ -v
```

CI pipeline: `.github/workflows/test-suite.yml` (quality, security, core pytest, and Playwright E2E jobs with artifact upload).

## Bug Reporting & Maintenance

To maintain a consistent `BUG_REPORT.md` across all AI agents (Claude, Gemini, etc.), use the provided management script:

```bash
# Add a new bug
python3 scripts/manage_bugs.py add "Bug Description" --severity critical --component "Backend" --impact "Crashes on startup"

# Update bug status
python3 scripts/manage_bugs.py update C-001 --status "Fixed"
```

AI agents should run this script whenever they identify a new bug or resolve an existing one.

**Known issue:** `manage_bugs.py` parsing may not align with current `BUG_REPORT.md` layout — always inspect `git diff` after running and revert if entries are incomplete.

## Architecture

```
Phone PWA ──WebSocket──▶ FastAPI ──ADK Runner──▶ Gemini 2.5 Flash (Live API)
  (camera+mic)           │                          │
                         │                     9 ADK Tools
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
- `agent/tools/` — 9 tool functions (smart search, asset lookup, work orders, safety, reports, human-in-the-loop confirmation)
- `api/websocket.py` — Bidirectional WebSocket handler using ADK `LiveRequestQueue` for audio/video/text streaming
- `api/websocket_helpers.py` — Confirmation execution, media card extraction helpers
- `api/routes.py` — REST endpoints for assets, work orders, inspections, knowledge base, confirmation flow, reports
- `services/eam_interface.py` — Abstract EAM service (pluggable: Firestore for hackathon, Hexagon EAM for production)
- `services/firestore_eam.py` — Firestore async implementation
- `services/base_eam.py` — Shared search helpers (searchable text construction, filter resolution, KB tokenization)
- `services/query_engine.py` — NLP pre-query intelligence layer (intent detection, ID normalization, synonym expansion, caching)
- `services/search_matcher.py` — Token-aware text matching with ASR domain corrections
- `services/confirmation_manager.py` — Human-in-the-loop action tracking (propose → confirm/reject/correct)
- `models/schemas.py` — Pydantic models (Asset, WorkOrder, EAMCode, InspectionRecord, etc.)

**Frontend** (`frontend/`): Vanilla HTML/CSS/JS PWA. No build step.
- `app.js` — Single-file client: WebSocket streaming, camera capture (2 FPS JPEG), mic capture (PCM 16kHz), audio playback (PCM 24kHz), confirmation card UI, 5-page data explorer with debounced search + filter dropdowns
- `index.html` — Three screens: splash, inspection (camera+agent), dashboard (5-page enterprise explorer: Work Orders, Assets, Locations, Knowledge Base, EAM Codes)
- `style.css` — Enterprise dashboard styles: sidebar nav (desktop), bottom nav (mobile), filter bars, data tables, status/priority badges

**Infrastructure**: Docker (Python 3.12-slim), Cloud Run (0-3 instances), Terraform, Cloud Build CI/CD.

**Local dev note:** Running under WSL2 — no camera/mic hardware available. Full audio/video E2E testing requires a real device or Cloud Run deployment.

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
- **Warning:** `.env` uses CRLF line endings — do NOT `source .env` directly in bash. Use `grep`/`cut`/`tr -d '\r'` to extract values.
