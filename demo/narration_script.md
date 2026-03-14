# Maintenance-Eye - Video Narration Script

Total target: **4:00** (240 seconds)
Read at a natural pace (~150 words/minute). Pause where indicated.

---

## ACT 1: HOOK + PROBLEM (0:00 - 0:35)
*Visuals: Title slide with "Maintenance-Eye" logo, then quick slides showing pain points*

> Every day, thousands of maintenance technicians inspect critical infrastructure - trains, escalators, power systems.
>
> When they find a fault, they stop what they're doing, pull out a clipboard or tablet, manually look up asset codes, search through work order systems, and type up reports - all while standing in noisy, sometimes dangerous environments.
>
> *[brief pause]*
>
> What if they could just... talk to their maintenance system?

---

## ACT 2: SOLUTION INTRO (0:35 - 1:05)
*Visuals: App splash screen, then inspection UI with camera view, then quick flash of dashboard*

> Meet Max - an AI co-pilot for infrastructure maintenance.
>
> Technicians point their phone camera at equipment, speak naturally, and Max identifies faults, looks up work orders, enforces safety protocols, and creates or closes work orders - all hands-free, all in real-time.
>
> Built with Google's Agent Development Kit and Gemini 2.5 Flash Live API, Max sees through the camera, hears through the mic, and speaks back - with full barge-in support.

---

## ACT 3: LIVE DEMO (1:05 - 3:05)

### Demo 1 transition (1:05 - 1:10)
*Visuals: Cut to on-site footage (Clip 3)*

> Here's Max in action at a real transit maintenance facility. Watch as the technician finds and closes a work order using only voice.

### Demo 1 plays (1:10 - 2:10)
*Play trimmed Clip 3 (PXL_20260305_184805027.mp4) - NO voice-over during this section, let the on-site audio play*

Clip should show:
1. Technician: "Currently working on train car 229 VOBC..."
2. Max finds 3 work orders, summarizes them
3. Technician: "Can you please close the one that you mentioned?"
4. Max: "Which open work order - the P1 or the P2?"
5. Technician: "The P1"
6. Max: "I've proposed closing... please confirm on your screen"
7. Technician taps Confirm button
8. Max: "Acknowledged. The P1 work order is now closed."

### Demo 1 callout (2:10 - 2:15)
*Visuals: Brief text overlay or return to slides*

> Notice how Max asked for clarification before acting, then required on-screen confirmation. That's human-in-the-loop safety built into every critical action.

---

### Demo 2 transition (2:15 - 2:20)
*Visuals: Cut to on-site footage (Clip 4)*

> Max also enforces safety procedures before any maintenance work begins.

### Demo 2 plays (2:20 - 2:40)
*Play trimmed Clip 4 (PXL_20260305_185052158.mp4) - let on-site audio play*

Clip should show:
1. Technician reports tacho fault
2. Max: "Before we proceed, please confirm the asset ID and that lockout tagout has been performed."
3. Technician: "Train car 212, and lockout tagout has been performed."

### Demo 2 callout (2:40 - 2:45)

> Safety-first by design. Max won't proceed without lockout-tagout confirmation.

---

### Demo 3 transition (2:45 - 2:48)

> Max also handles real-world interruptions naturally.

### Demo 3 plays (2:48 - 3:05)
*Quick montage - play trimmed clips back to back*

**Part A** - Clip 1 (PXL_20260305_184128256.mp4), trimmed to ~10s:
- Technician: "I don't see anything on my screen"
- Max: "One moment. I've re-sent the proposal... please check your screen."
- Technician taps Confirm

**Part B** - Clip 6 (PXL_20260305_185306540.mp4), trimmed to ~7s:
- Max: "Could you please provide more context? The term 'VOB' isn't standard in our system..."

*Optional text overlay: "Barge-in + Error Recovery" and "Intelligent Clarification"*

---

## ACT 4: ARCHITECTURE + TECH (3:05 - 3:45)
*Visuals: Architecture diagram (full screen, hold for ~15s), then GCP console screen recording, then quick code flash*

> Under the hood, Maintenance-Eye is built entirely on Google Cloud.
>
> The phone connects via WebSocket to a FastAPI backend running on Cloud Run. Google's Agent Development Kit orchestrates the agent with nine specialized tools - including asset lookup, work order management, safety protocols, and a knowledge base.
>
> Gemini 2.5 Flash Live API handles real-time audio and vision streaming. Firestore stores all the enterprise asset management data.
>
> *[switch to GCP console recording]*
>
> Here's our service running on Cloud Run, deployed with automated scripts and Terraform.

---

## ACT 5: CLOSING (3:45 - 4:00)
*Visuals: Closing slide with project name, GitHub URL, tech stack logos (Google Cloud, ADK, Gemini, Firestore, Cloud Run)*

> Maintenance-Eye turns every technician into a hands-free, AI-powered maintenance expert.
>
> Built with Google ADK and Gemini Live API, for the Gemini Live Agent Challenge.
>
> Thank you.

---

## Word Count Summary

| Section | Words | Est. Duration |
|---------|-------|---------------|
| ACT 1 | ~70 | ~30s |
| ACT 2 | ~75 | ~30s |
| ACT 3 (voice-over only) | ~65 | ~25s (rest is demo audio) |
| ACT 4 | ~75 | ~30s |
| ACT 5 | ~30 | ~12s |
| **Total narration** | **~315** | **~127s** |
| Demo clips (on-site audio) | - | ~113s |
| **Grand total** | | **~240s (4:00)** |

## Recording Tips

- Record in a quiet room with minimal echo
- Speak slightly slower than conversational pace
- Emphasize key terms: "hands-free", "real-time", "barge-in", "human-in-the-loop", "safety-first"
- Pause briefly (1s) between sections for editing flexibility
- Record each ACT as a separate take for easier editing
