# Agent Topology and Execution State Framework

## 1. Orchestration Model: Directed Acyclic Graphs (DAG)
The platform rejects general agent frameworks that cause high token bloat. It runs on a deterministic, typed state machine where sub-agents pass strongly typed data contracts through Pydantic guardrails.

## 2. Sub-Agent Structural Contracts

### A. The Research and Grounding Agent
- **Model Target:** `gemini-3.1-flash-lite`
- **Configuration:** `generationConfig: {"responseMimeType": "text/plain"}, tools: [{"googleSearch": {}}]`
- **Execution Domain:** Ingests raw seeds, browses the web using Google Search grounding, strips tracking scripts, and outputs a single, clean **Unified Truth Document (UTD)**.

### B. The Omni-Channel Copywriting Agent
- **Model Target:** `deepseek/deepseek-v4-flash:free`
- **Configuration:** Strict JSON schema validation mapping to the platform payload schema.
- **Execution Domain:** Transforms the text profile of the UTD into structured layout variants for every target platform concurrently.

### C. The Real-Time Voice Proxy Agent
- **Model Target:** `gemini-2.5-flash-native-audio-preview`
- **Configuration:** Direct bi-directional binary audio streaming over WebSockets.
- **Execution Domain:** Connects inside the LiveKit transport track to listen to call participants, handle verbal interruptions, track screen-shares visually, and respond using an optimized custom voice clone.

## 3. The Asymmetric Critic Verification Loop
Before any generated content reaches the human dashboard or automated deployment queues, it undergoes strict cross-examination:

[Generated Asset Array (JSON)] ──► [NVIDIA Nemotron 3 Super (Critic Mode)]
│
┌────────────────────────┴────────────────────────┐
▼ (Passed Validation)                             ▼ (Flagged Jargon/Errors)
[Push to Frontend Queue]                         [Trigger Self-Healing Routine]