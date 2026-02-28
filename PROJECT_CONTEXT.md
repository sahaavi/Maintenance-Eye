# Maintenance-Eye — Project Context

> **Purpose**: This file provides persistent context for AI assistants and LLMs.
> Read this file first to understand the project without needing re-explanation.

## Project Overview

**Maintenance-Eye** is an enterprise-grade AI co-pilot for physical infrastructure maintenance operations, built for the [Google Gemini Live Agent Challenge](https://devpost.com/) hackathon.

A field technician points their phone camera at equipment, speaks naturally, and the agent:
- **Sees** equipment conditions via live camera
- **Identifies** faults, wear, anomalies in real-time
- **Speaks** findings with severity and confidence scores
- **Auto-classifies** using EAM codes (Problem/Fault/Action)
- **Creates work orders** with technician confirmation
- **Generates inspection reports** with photos and findings
- Supports **natural interruptions** (barge-in)

**Category**: Live Agents (real-time audio/vision interaction)

## Hackathon Details

- **Rules**: See `hackathon/rules.md`
- **Submission deadline**: Before March 17, 2026
- **Judging**: Mar 17 – Apr 3, 2026
- **Winners Announced**: Apr 22–24, 2026 at Google NEXT
- **Submission**: Devpost

## Developer

- **Name**: Avishek Saha
- **Working solo**, ~75 hours total, $50 CAD budget
- **Skills**: Python, intermediate AI/ML & GCP, Vertex AI experience
- **Domain Expertise**: Finance, tech, asset management — works at BCRTC Skytrain
- **No GDG membership**

## Domain Context (CRITICAL)

The system is modeled after real SkyTrain maintenance operations:
- **6 departments**: Rolling Stock, Guideway, Power, Signal & Telecom, Facilities, Elevating Devices
- **Zone Technicians** are highly experienced field techs with only phones
- Current process: manual inspection, tribal knowledge, paper-based reporting
- **Hexagon EAM** is the real enterprise system (we use a synthetic abstraction)
- Work orders require structured codes: Problem Code, Fault Code, Action Code, Equipment Code
- System uses **synthetic data** but is **enterprise-compatible** via an EAM abstraction layer

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML/JS PWA (mobile-first) |
| Backend | Python + FastAPI on Cloud Run |
| AI | Gemini 2.5 Flash via Live API |
| Agent | Google ADK (Agent Development Kit) |
| Database | Firestore (synthetic EAM data) |
| Storage | Cloud Storage (photos, reports) |
| Auth | Firebase Auth |
| Deployment | Terraform + Cloud Build |

## ADK Agent Tools

| Tool | Purpose |
|---|---|
| `lookup_asset` | Find asset by name/code/GPS |
| `get_inspection_history` | Past inspections & failure patterns |
| `search_knowledge_base` | Search repair procedures & manuals |
| `manage_work_order` | Create/update WOs with auto-classified EAM codes |
| `get_safety_protocol` | Safety procedures, LOTO, PPE |
| `generate_report` | Inspection summary with photos |

## Key Judging Criteria

1. **Innovation & Multimodal UX (40%)** — "Beyond text", barge-in, persona
2. **Technical Implementation (30%)** — Cloud-native, ADK/GenAI SDK, robustness
3. **Demo & Presentation (30%)** — Problem story, architecture diagram, live demo

## Bonus Points Plan

- [ ] Blog post on dev.to (+0.6 max)
- [ ] Automated cloud deployment via Terraform (+0.2)
- [x] GDG membership (+0.2) — N/A (not a member)

## Key Decisions Log

| Date | Decision |
|---|---|
| 2026-02-24 | Project selected: Live visual inspection agent (Live Agents category) |
| 2026-02-24 | Architecture: ADK + Gemini Live API + Firestore EAM abstraction |
| 2026-02-24 | Removed Vertex AI Vision — Gemini native vision sufficient |
| 2026-02-24 | Synthetic data approach for EAM with enterprise-compatible abstraction |

## Status

**Phase**: Planning — implementation plan under review before execution begins.
