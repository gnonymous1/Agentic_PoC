<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:020813,35:05182e,70:092b4a,100:0e446c&height=180&section=header&text=GNONE&fontSize=40&fontColor=00f0ff&desc=Sovereign%20Executive%20Proxy%20Engine&descSize=15&descAlignY=55" width="100%"/>

<br/>

[![Status](https://img.shields.io/badge/STATUS-ACTIVE-00f0ff?style=for-the-badge&labelColor=0d1117)](#)
[![Visibility](https://img.shields.io/badge/VISIBILITY-PRIVATE-ff0055?style=for-the-badge&labelColor=0d1117)](#)
[![Stack](https://img.shields.io/badge/ENGINE-FASTAPI_%7C_LIVEKIT_%7C_GEMINI-00ff66?style=for-the-badge&labelColor=0d1117)](#)

</div>

---

## 01 // OVERVIEW

**GNONE (Sovereign Executive Proxy Engine)** is an advanced, enterprise-grade distributed multi-agent AI system designed to act as an autonomous digital clone and proxy for executive communication, real-time virtual meeting participation, and multi-channel content publishing. 

Designed for high-concurrency environments, it handles low-latency WebRTC audio/video manipulation alongside parallel event-driven social media dispatching, ensuring a seamless digital presence without manual intervention.

---

## 02 // KEY ARCHITECTURAL FEATURES

*   **🎙️ Real-Time Voice Proxy Agent:** Built on the `Pipecat` framework running over `LiveKit Server` worker threads. Direct bi-directional WebRTC streaming using `gemini-2.5-flash-native-audio-preview` processes real-time voice, interrupts, and screen shares to speak and act as a digital clone during meetings.
*   **📅 Recall.ai Container Integration:** Spawns isolated, headless Linux virtualization blocks running hardware-accelerated Chromium instances to autonomously join Zoom, Microsoft Teams, and Google Meet sessions.
*   **🤖 Asymmetric Critic Verification Loop:** Before any generated content reaches the dashboard or automated deployment queues, it undergoes strict cross-examination using an validation node (NVIDIA Nemotron 3 Super Critic) to check for jargon or errors, triggering a self-healing compiler loop if needed.
*   **🔗 Directed Acyclic Graph (DAG) Orchestrator:** Bypasses general-agent token bloat. Relies on a deterministic, strongly typed state machine (`dag_orchestrator.py`) where sub-agents pass typed data contracts using Pydantic guardrails.
*   **📱 Multi-Platform Social Ingestion & Dispatcher:** Parallel task handlers publish updates to Facebook Graph, Instagram, X (Twitter), LinkedIn, and Google Blogger.
*   **💻 Neuro-Symbolic Streamlit Dashboard:** Provides real-time tracking, log monitoring, and Human-in-the-Loop (HITL) gatekeeping for critical messages before publishing.

---

## 03 // SYSTEM TOPOLOGY

```
[Ingestion: Webhook / Calendar / RSS / API Streams]
                       │
                       ▼
    [FastAPI Central Microservice Gateway]
                       │
┌──────────────────────┴──────────────────────┐
▼ (Asynchronous Track)                        ▼ (Real-Time Track)
[Social Media & Inbox Engine]              [Recall.ai Container Manager]
├── Meta Graph Cluster (FB/IG)             └── Headless Linux Chromium Box
├── X API v2 Pipeline                      └── Zoom / Meet / Teams Session
├── LinkedIn Enterprise OAuth                               │
└── Google Blogger API Engine                               ▼
                                           [LiveKit Server Stream Matrix]
                                           │ (WebRTC Audio/Vision Tracks)
                                           ▼
                                           [Gemini Live Engine Core]
                                           (WSS Native Audio Preview)
                                           │
                                           ▼
                                           [Low-Latency Voice Transport]
```

---

## 04 // AGENT ROLES & MODEL MAPPING

| Sub-Agent | Model Target | Tools / Protocol | Operational Domain |
| :--- | :--- | :--- | :--- |
| **Research & Grounding** | `gemini-3.1-flash-lite` | Google Search Tool | Ingests raw seeds, browses the web, strips tracking script telemetry, and generates a **Unified Truth Document (UTD)**. |
| **Omni-Channel Copywriting** | `deepseek-v4-flash` | Strict JSON schema mapping | Transforms the text profile of the UTD into structured layout variants for every target social platform concurrently. |
| **Real-Time Voice Proxy** | `gemini-2.5-flash-native-audio` | WebSocket WebRTC Binary Streams | Connects to LiveKit rooms, handles verbal interruptions, tracks screen-shares, and responds using a custom voice clone. |

---

## 05 // CODEBASE LAYOUT

```text
/GNONE/
├── api/                           # Endpoint controllers (Authentication, Webhooks, API)
├── app/                           # Core application startup configurations
├── database/                      # DB connections, pgvector search setup, models
├── digital_clone/                 # LiveKit audio models and voice-cloning configurations
├── docs/                          # API and agent topology specs
├── tests/                         # Multi-agent unit and integration test suite
├── dag_orchestrator.py            # Main state-machine DAG execution pipeline
├── dashboard.py                   # Streamlit control panel backend
├── hitl_gateway.py                # Human-In-The-Loop gatekeeping logic
├── meeting_proxy.py               # Recall.ai interface & connection controller
├── content_engine.py              # Social media content parsing and dispatching
├── requirements.txt               # Main service requirements
└── docker-compose.yml             # Local Redis, Postgres, and core backend orchestration
```

---

## 06 // QUICK START

### 1. Configure Environment Variables
Copy `.env.example` to `.env` and fill in the required API credentials:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```ini
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key
RECALL_AI_API_KEY=your_recall_key
LIVEKIT_API_KEY=your_livekit_key
LIVEKIT_API_SECRET=your_livekit_secret
```

### 2. Local Stack Launch
Spin up Redis and PostgreSQL containers:
```bash
docker-compose up -d
```

### 3. Initialize Server and Dashboard
Run the start script to boot the FastAPI microservices and Streamlit UI:
```bash
start.bat
```
The Streamlit dashboard will be available at `http://localhost:8501`.
