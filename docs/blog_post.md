# Building Maintenance-Eye: Bridging the Gap Between AI and Transit Infrastructure

*How we used the Google ADK and Gemini Live API to create a real-time AI co-pilot for maintenance technicians.*

---

## The Challenge: Maintenance in the Dark
In the world of transit infrastructure—escalators, switch machines, and power transformers—maintenance is often a manual, high-stakes process. Technicians work in high-pressure environments, often with their hands occupied, while trying to follow complex safety protocols and record data into Enterprise Asset Management (EAM) systems.

The problem? Traditional software requires "stopping and typing." We wanted to build something that lives *with* the technician: **Maintenance-Eye**.

## Our Solution: A Hands-Free AI Co-Pilot
Maintenance-Eye is an AI co-pilot that helps technicians perform inspections in real-time. By leveraging the **Gemini Live API** and the **Google Agent Development Kit (ADK)**, we created an agent named "Max" who can:
- **See** through the phone's camera to identify faults like corrosion or wear.
- **Speak** and listen in real-time, providing safety briefings and repair steps.
- **Ground** its advice in actual asset data and maintenance manuals.
- **Automate** EAM data entry by proposing work orders for human confirmation.

---

## Technical Architecture: The "Bidi-Streaming" Core

The heart of Maintenance-Eye is a bidirectional streaming architecture. Unlike traditional Request-Response cycles, we needed a persistent connection that could handle audio, video, and tool calls simultaneously.

### 1. The Google ADK Runner
We used the **Google ADK Runner** to orchestrate the "brain" of our application. The ADK allowed us to define a complex persona and bind it to a suite of powerful tools:
- `lookup_asset`: Grounding the AI in the specific equipment's history.
- `search_knowledge_base`: Pulling repair procedures from technical manuals.
- `propose_action`: A critical "Human-in-the-Loop" tool that ensures the AI never acts without technician approval.

### 2. Bidirectional Streaming (FastAPI + WebSockets)
On the backend, we implemented a FastAPI WebSocket handler that bridges the mobile PWA to the Gemini Live API. 
- **Upstream**: PCM 16kHz audio and JPEG video frames are streamed to the ADK `LiveRequestQueue`.
- **Downstream**: The agent’s PCM 24kHz audio, text transcripts, and tool results are streamed back to the technician.

### 3. Beyond Text: The Multimodal HUD
To make the experience truly "Beyond Text," we built a Heads-Up Display (HUD) in the PWA. When the agent uses a tool—like looking up a repair manual—it doesn't just "say" the steps. The backend intercepts the tool result and pushes a **Rich Media Card** to the technician's screen.

---

## Key Feature: Human-in-the-Loop (AI Safety)
One of our core goals was **Reliability**. We used the ADK to implement a strict confirmation workflow. Max cannot create a work order alone. He must call the `propose_action` tool, which renders a physical "Confirmation Card" in the UI. The technician can:
- **Confirm** (proceed with the AI's recommendation)
- **Reject** (stop the action)
- **Correct** (edit the priority or problem code manually)

This ensures the AI is a *tool* for the technician, not a replacement for their expertise.

---

## Why Maintenance-Eye Wins
- **Grounding**: We seeded our database with 80+ realistic assets and 25+ maintenance procedures. Max isn't hallucinating; he's reading your manuals.
- **Multimodal UX**: A HUD overlay with scanning animations and interleaved media cards makes the AI feel alive.
- **Enterprise Ready**: Designed for scale with Google Cloud Firestore, GCS, and a structured EAM data model.

## What’s Next?
We believe AI co-pilots like Max are the future of industrial work. By removing the friction of data entry and providing real-time safety guardrails, we can make infrastructure maintenance safer, faster, and more accurate.

---

*Check out Maintenance-Eye on [GitHub URL]*
*Built for the Google Gemini Live Agent Challenge 2026.*
