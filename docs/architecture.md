# Maintenance-Eye Architecture Diagram

Copy the Mermaid code below into [mermaid.live](https://mermaid.live) to render and export as PNG for the video.

```mermaid
flowchart LR
    subgraph CLIENT["📱 Phone PWA"]
        CAM["Camera<br/>2 FPS JPEG"]
        MIC["Microphone<br/>PCM 16kHz"]
        SPK["Speaker<br/>PCM 24kHz"]
        UI["Confirmation<br/>Card UI"]
    end

    subgraph GCP["☁️ Google Cloud"]
        subgraph CR["Cloud Run"]
            subgraph BACKEND["FastAPI Backend"]
                WS["WebSocket<br/>Handler"]
                REST["REST API"]
                CM["Confirmation<br/>Manager"]
            end

            subgraph ADK["Google ADK Agent"]
                RUNNER["ADK Runner<br/>+ LiveRequestQueue"]
                TOOLS["9 Agent Tools"]
            end
        end

        GEMINI["Gemini 2.5 Flash<br/>Live API<br/>(native audio)"]
        FS["Cloud Firestore<br/>(EAM Data)"]
        GCS["Cloud Storage<br/>(Photos)"]
    end

    CAM -- "video frames" --> WS
    MIC -- "audio stream" --> WS
    WS -- "audio stream" --> SPK
    WS -- "confirmation cards" --> UI
    UI -- "confirm / reject" --> WS

    WS <--> RUNNER
    RUNNER <--> GEMINI
    GEMINI --> TOOLS

    TOOLS --> |"lookup_asset<br/>smart_search<br/>manage_work_order<br/>get_safety_protocol<br/>propose_action<br/>..."| FS
    TOOLS --> GCS
    REST <--> FS
    CM <--> WS

    style CLIENT fill:#1565C0,stroke:#0D47A1,stroke-width:2px,color:#FFFFFF
    style GCP fill:#2E7D32,stroke:#1B5E20,stroke-width:2px,color:#FFFFFF
    style CR fill:#E65100,stroke:#BF360C,stroke-width:2px,color:#FFFFFF
    style BACKEND fill:#F57F17,stroke:#F9A825,stroke-width:1px,color:#000000
    style ADK fill:#7B1FA2,stroke:#4A148C,stroke-width:2px,color:#FFFFFF
    style GEMINI fill:#C62828,stroke:#B71C1C,stroke-width:2px,color:#FFFFFF
    style FS fill:#00695C,stroke:#004D40,stroke-width:2px,color:#FFFFFF
    style GCS fill:#00695C,stroke:#004D40,stroke-width:2px,color:#FFFFFF

    style CAM fill:#BBDEFB,stroke:#1565C0,stroke-width:1px,color:#0D47A1
    style MIC fill:#BBDEFB,stroke:#1565C0,stroke-width:1px,color:#0D47A1
    style SPK fill:#BBDEFB,stroke:#1565C0,stroke-width:1px,color:#0D47A1
    style UI fill:#BBDEFB,stroke:#1565C0,stroke-width:1px,color:#0D47A1

    style WS fill:#FFF8E1,stroke:#F57F17,stroke-width:1px,color:#000000
    style REST fill:#FFF8E1,stroke:#F57F17,stroke-width:1px,color:#000000
    style CM fill:#FFF8E1,stroke:#F57F17,stroke-width:1px,color:#000000

    style RUNNER fill:#E1BEE7,stroke:#7B1FA2,stroke-width:1px,color:#4A148C
    style TOOLS fill:#E1BEE7,stroke:#7B1FA2,stroke-width:1px,color:#4A148C
```

## How to export

1. Go to [mermaid.live](https://mermaid.live)
2. Paste the Mermaid code above (everything between the triple backticks)
3. Adjust theme if needed (try "dark" for a video-friendly background)
4. Click the download PNG button (or SVG)
5. Use the exported image in your video during the Architecture section (ACT 4, ~3:05-3:45)
