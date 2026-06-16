# GNONE Multi-Agent Systems Architecture Report

**Platform:** GNONE — Sovereign Executive Proxy Engine
**Author:** Multi-Agent Systems Architecture Review
**Date:** May 2026
**Version:** 1.0.0

---

## Table of Contents

1. [Agent Architecture Overview](#1-agent-architecture-overview)
2. [DAG Orchestration Engine](#2-dag-orchestration-engine)
3. [Agent Contract System](#3-agent-contract-system)
4. [Tool Integration Pattern](#4-tool-integration-pattern)
5. [Agent Memory & State](#5-agent-memory--state)
6. [Real-Time Agent: VoiceProxyAgent](#6-real-time-agent-voiceproxyagent)
7. [MCP (Model Context Protocol) Readiness](#7-mcp-model-context-protocol-readiness)
8. [Agent Observability](#8-agent-observability)
9. [Multi-Agent Failure Modes](#9-multi-agent-failure-modes)
10. [Future Agent Architecture](#10-future-agent-architecture)

---

## 1. Agent Architecture Overview

GNONE implements a deterministic, typed state machine architecture where five specialized sub-agents pass strongly typed data contracts through Pydantic guardrails. The platform explicitly rejects general-purpose agent frameworks that cause high token bloat, instead building a lean DAG-based orchestration layer with zero framework overhead beyond Python's standard library.

### 1.1 Agent Inventory

| Agent | Model Target | Role | File |
|-------|-------------|------|------|
| **ResearchAgent** | `gemini-3.1-flash-lite` | Web grounding + UTD generation | `app/agents/research_agent.py` |
| **CopywritingAgent** | `openai/gpt-oss-120b:free` | Multi-platform content drafting | `app/agents/copywriting_agent.py` |
| **CriticAgent** | `nvidia/nemotron-3-super:free` | Adversarial QA + self-healing loop | `app/agents/critic_agent.py` |
| **ModeratorAgent** | (rule-based regex) | Content safety scanning | `app/agents/moderator_agent.py` |
| **VoiceProxyAgent** | `gemini-2.5-flash-native-audio-preview` | Real-time audio/video meeting proxy | `app/agents/voice_agent.py` |

### 1.2 Class Hierarchy

```
BaseAgent (ABC)                          # app/agents/base.py
├── ResearchAgent                         # app/agents/research_agent.py
├── CopywritingAgent                      # app/agents/copywriting_agent.py
├── CriticAgent                           # app/agents/critic_agent.py
├── ModeratorAgent                        # app/agents/moderator_agent.py
└── VoiceProxyAgent                       # app/agents/voice_agent.py

DAGOrchestrator                           # app/core/orchestrator.py
├── register(agent, depends_on)
└── run(ctx) -> AgentContext

AgentContext (dataclass)                  # app/core/orchestrator.py
├── correlation_id: str
├── topic: str
├── unified_truth_document: str
├── generated_content: dict
├── critic_approved: bool
├── refinement_cycles: int
├── brand_voice: str
└── errors: list[dict]

AgentNode (dataclass)                     # app/core/orchestrator.py
├── name: str
├── dependencies: list[str]
├── status: AgentStatus
├── retry_count: int
└── max_retries: int
```

### 1.3 Agent Lifecycle

Each agent in the pipeline transitions through a well-defined state machine. The `AgentStatus` enum (`app/core/orchestrator.py:13`) defines the canonical states:

```
                  ┌─────────┐
                  │ PENDING │
                  └────┬────┘
                       │
                  ┌────▼────┐
         ┌────────│ RUNNING │────────┐
         │        └────┬────┘        │
         ▼             ▼             ▼
   ┌─────────┐   ┌──────────┐  ┌─────────┐
   │SUCCEEDED│   │  HEALING │  │ FAILED  │
   └─────────┘   └────┬─────┘  └─────────┘
                      │ (retry)
                      ▼
                  ┌─────────┐
                  │ RUNNING │
                  └─────────┘
```

- **PENDING**: Agent is registered in the DAG but not yet executed
- **RUNNING**: Agent's `execute()` method is active
- **SUCCEEDED**: Agent completed without raising an exception
- **FAILED**: Agent exhausted all retry attempts
- **HEALING**: Agent failed but is mid-retry (transient state)
- **SKIPPED**: Upstream dependency failed, so downstream agent was never executed

### 1.4 Agent Communication Protocol

Agents communicate exclusively through the `AgentContext` dataclass (`app/core/orchestrator.py:23`), which serves as the shared memory bus for the entire pipeline. The context flows forward through the DAG — agents read fields produced by upstream agents and write fields consumed by downstream agents.

```
Communication Flow:

ResearchAgent ──► ctx.unified_truth_document
                         │
                         ▼
                 CopywritingAgent ──► ctx.generated_content
                                              │
                                              ▼
                                      CriticAgent ──► ctx.critic_approved
                                              │       ctx.refinement_cycles
                                              │
                                              ▼
                                      ModeratorAgent ──► ctx.metadata["moderator_verdict"]
```

No agent communicates via side channels (no direct HTTP calls between agents, no shared database writes mid-pipeline). This guarantees that any agent can be replayed or replaced without side effects, and the full pipeline state is captured in a single serializable object.

---

## 2. DAG Orchestration Engine

### 2.1 Graph Construction

The `DAGOrchestrator` class (`app/core/orchestrator.py:84`) builds a directed acyclic graph of agents using Python's built-in `graphlib.TopologicalSorter`. Agents register with optional dependency declarations:

```python
orchestrator = DAGOrchestrator()
orchestrator.register(ResearchAgent())                              # root node
orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])
orchestrator.register(CriticAgent(), depends_on=["copywriting_agent"])
orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])
```

The internal graph structure is a `dict[str, list[str]]` mapping each agent name to its dependency list:

```python
self._graph = {
    "research_agent": [],
    "copywriting_agent": ["research_agent"],
    "critic_agent": ["copywriting_agent"],
    "moderator_agent": ["critic_agent"],
}
```

### 2.2 Dependency Resolution

`TopologicalSorter.static_order()` produces a linear execution plan respecting all dependency constraints:

```
Execution Plan (linearized):
1. research_agent              (no dependencies)
2. copywriting_agent           (depends on research_agent)
3. critic_agent                (depends on copywriting_agent)
4. moderator_agent             (depends on critic_agent)
```

The orchestrator iterates through this plan sequentially. For each agent, it checks whether any dependency has FAILED status. If so, the agent is SKIPPED and the pipeline continues (other independent branches can still execute).

### 2.3 Parallel Execution Model

While the current pipeline is strictly sequential (each agent depends on the previous one), the orchestrator architecture supports parallel branches. Consider a future pipeline:

```
          ┌──────────────────┐
          │ research_agent   │
          └────────┬─────────┘
                   │
          ┌────────┴────────┐
          ▼                 ▼
  ┌──────────────┐  ┌──────────────┐
  │ twitter_agent│  │ linkedin_agent│  (parallel)
  └──────────────┘  └──────────────┘
          │                 │
          └────────┬────────┘
                   ▼
          ┌──────────────────┐
          │ publishing_agent │
          └──────────────────┘
```

TopologicalSorter handles this natively — parallel agents would execute concurrently via `asyncio.gather` in a future implementation. The current `run()` method is sequential to maintain simplicity, but the graph model permits parallelism at the architectural level.

### 2.4 Upstream Failure Propagation

When an agent fails (exhausts retries), all downstream agents that declared a dependency on it receive SKIPPED status:

```python
# app/core/orchestrator.py:114-122
if any(
    self._nodes[dep].status == AgentStatus.FAILED
    for dep in node.dependencies
):
    node.status = AgentStatus.SKIPPED
    continue
```

This prevents wasted computation and API costs on content that cannot be completed. The SKIPPED status propagates transitively: if CopywritingAgent fails, CriticAgent AND ModeratorAgent are both skipped.

### 2.5 Retry Logic with Exponential Backoff

Each agent has a configurable `max_retries` (default: 3). On failure, the orchestrator:

1. Sets node status to HEALING
2. Waits `1.0 * attempt_number` seconds (linear backoff)
3. Re-executes the agent's `run()` method
4. If all retries exhausted, sets status to FAILED and raises the original exception

```python
# app/core/orchestrator.py:127-143
for attempt in range(1, node.max_retries + 1):
    try:
        ctx = await agent.run(ctx)
        node.status = AgentStatus.SUCCEEDED
        break
    except Exception as e:
        node.retry_count = attempt
        if attempt < node.max_retries:
            node.status = AgentStatus.HEALING
            await asyncio.sleep(1.0 * attempt)
        else:
            node.status = AgentStatus.FAILED
            raise
```

### 2.6 Execution Plan Visualization

The orchestrator exposes `_build_execution_plan()` which can be used to generate text-based or Mermaid visualization of the agent DAG:

```
┌─────────────────────────────────────────────────────┐
│               DAG Execution Plan                     │
├─────────────────────────────────────────────────────┤
│                                                       │
│  research_agent ──────────────────────────────────┐  │
│                                                    │  │
│  copywriting_agent ◄── depends_on: research_agent  │  │
│                                                    │  │
│  critic_agent ◄── depends_on: copywriting_agent    │  │
│                                                    │  │
│  moderator_agent ◄── depends_on: critic_agent      │  │
│                                                    │  │
│  Order: research → copywriting → critic → moderator │
│                                                       │
└─────────────────────────────────────────────────────┘
```

---

## 3. Agent Contract System

Every agent boundary in GNONE is enforced by a Pydantic model that defines the exact shape of data passing between agents. These contracts serve as runtime guardrails — if any agent produces malformed output, Pydantic's validation raises immediately, preventing context corruption from propagating downstream.

### 3.1 Contract Inventory

#### ResearchContract (`app/models/agent_contracts.py:12`)

```python
class ResearchContract(BaseModel):
    topic: str
    unified_truth_document: str = Field(..., min_length=200)
    source_domains: list[str] = Field(default_factory=list)
    unverified_claims: list[str] = Field(default_factory=list)
    research_timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
```

**Validation rules:**
- UTD must be at least 200 characters and 50 words
- `confidence_score` clamped to [0.0, 1.0]
- Sources MUST be cited inline in [brackets] (enforced by Gemini system prompt, not Pydantic)

**Purpose:** Pipelines the output of ResearchAgent into CopywritingAgent. Guarantees the copywriter always receives a minimum viable corpus.

#### CopywritingContract (`app/models/agent_contracts.py:30`)

```python
class CopywritingContract(BaseModel):
    utd_summary: str = Field(..., max_length=500)
    twitter_thread: list[str] = Field(..., min_length=5, max_length=10)
    linkedin_body: str = Field(..., min_length=50)
    facebook_body: str = Field(..., min_length=50)
    blogspot_html: str = Field(..., min_length=300)
```

**Validation rules:**
- Twitter posts: exactly 5–10 items, each ≤ 240 characters
- LinkedIn body: minimum 50 characters
- Blogspot HTML: minimum 300 characters

**Purpose:** Ensures every platform gets complete, publishable content before the critic reviews it.

#### CriticVerdict (`app/models/agent_contracts.py:47`)

```python
class CriticVerdict(BaseModel):
    approved: bool
    refinement_notes: str = ""
    corrected_payloads: dict = Field(default_factory=dict)
    banned_phrases_found: list[str] = Field(default_factory=list)
    structural_issues: list[str] = Field(default_factory=list)
    critic_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
```

**Purpose:** Transports the critic's verdict back into the CriticAgent context. If not approved, `refinement_notes` is fed back into the copywriter for regeneration.

#### ModeratorVerdict (`app/models/agent_contracts.py:57`)

```python
class ModeratorVerdict(BaseModel):
    passed_safety_check: bool
    content_safe: bool = True
    flagged_categories: list[str] = Field(default_factory=list)
    moderation_notes: str = ""
    moderated_content: Optional[dict] = None
```

**Purpose:** Declares whether content passes safety screening. If any FLAGGED_PATTERNS are matched, the content is blocked from publishing.

#### DeploymentContract (`app/models/agent_contracts.py:66`)

```python
class DeploymentContract(BaseModel):
    request_id: str
    client_id: str
    platform: str
    content_body: str
    scheduled_at: Optional[datetime] = None
    dry_run: bool = False
```

**Purpose:** The final contract issued when content is ready for platform dispatching. Each platform gets its own DeploymentContract instance.

### 3.2 Contract Enforcement Diagram

```
Agent Boundary Contract Enforcement:

┌──────────────────┐     ResearchContract     ┌──────────────────┐
│  ResearchAgent   │ ───────────────────────► │ CopywritingAgent │
│  (output)        │   topic, utd, sources    │  (input)         │
└──────────────────┘                          └────────┬─────────┘
                                                       │
                                 CopywritingContract    │
                                                       ▼
                                              ┌──────────────────┐
                                              │   CriticAgent    │
                                              │  (input/output)  │
                                              └────────┬─────────┘
                                                       │
                                        CriticVerdict   │
                                                       ▼
                                              ┌──────────────────┐
                                              │ ModeratorAgent   │
                                              │  (input)         │
                                              └────────┬─────────┘
                                                       │
                                    ModeratorVerdict    │
                                                       ▼
                                              ┌──────────────────┐
                                              │ DeploymentQueue  │
                                              │  (output)        │
                                              └──────────────────┘
```

### 3.3 Contract Violation Handling

When Pydantic validation fails, the `AgentContractViolation` exception (`app/core/errors.py:14`) is raised:

```python
class AgentContractViolation(GNONEBaseError):
    def __init__(self, agent_name: str, field: str, detail: str):
        super().__init__(
            message=f"Agent '{agent_name}' violated contract on field '{field}': {detail}"
        )
```

This error includes the offending agent name, the field that failed, and the validation detail, enabling precise debugging without log spelunking.

---

## 4. Tool Integration Pattern

GNONE agents do not call external APIs directly. All tool integration is abstracted through a dedicated service layer (`app/services/`). This separation allows model providers to be swapped without changing agent logic, and enables consistent cross-cutting concerns (circuit breaking, rate limiting, tracing) to be applied at the service boundary.

### 4.1 Service Layer Architecture

```
Agent Layer                    Service Layer                     External API
┌────────────┐     call     ┌──────────────────┐     HTTP     ┌──────────────┐
│ResearchAgent│──────────►  │gemini_grounding  │─────────────►│ Gemini API   │
└────────────┘              │  .research_topic │              │ + Google     │
                            └──────────────────┘              │   Search     │
┌────────────┐     call     ┌──────────────────┐     HTTP     └──────────────┘
│Copywriting │──────────►  │openrouter_       │─────────────►│ OpenRouter   │
│  Agent     │              │ generator.py     │              │ → GPT OSS    │
└────────────┘              └──────────────────┘              │   120B       │
                            ┌──────────────────┐     HTTP     └──────────────┘
┌────────────┐     call     │ critic_loop.py   │─────────────►│ OpenRouter   │
│CriticAgent │──────────►  │                  │              │ → Nemotron   │
└────────────┘              └──────────────────┘              │   3 Super    │
                                                              └──────────────┘
┌────────────┐     call     ┌──────────────────┐     TCP      ┌──────────────┐
│VoiceProxy  │──────────►  │ livekit_service  │─────────────►│ LiveKit      │
│  Agent     │              │  .py             │ WebRTC       │ Server       │
└────────────┘              └──────────────────┘              └──────────────┘
```

### 4.2 Gemini Research Agent: Google Search Tool

The `gemini_grounding.py` service (`app/services/gemini_grounding.py`) uses Gemini's native `googleSearch` tool for real-time web browsing. The API payload includes:

```json
{
  "tools": [{"googleSearch": {}}],
  "generationConfig": {
    "responseMimeType": "text/plain",
    "temperature": 0.3
  }
}
```

**Key behaviors:**
- Strips tracking scripts, affiliate links, clickbait, and paywalled filler via `_strip_tracking_fluff()`
- Enforces minimum 50-word UTD output, otherwise raises `ValueError` to trigger HEALING retry
- Sources MUST be cited inline in `[brackets]` with domain names
- Unverifiable facts marked as `[UNVERIFIED]`

### 4.3 Copywriting & Critic Agents: JSON Mode

Both the copywriting generator and the critic use OpenRouter's `response_format: {"type": "json_object"}` to enforce structured output:

```python
payload = {
    "model": settings.generator_model,
    "response_format": {"type": "json_object"},
    "messages": [
        {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ],
}
```

The copywriting agent's system prompt (120 lines in `openrouter_generator.py`) enforces:
- Twitter: 5-10 posts, each ≤ 240 characters
- LinkedIn: professional executive tone with bullet points
- Facebook: conversational with CTA
- Blogspot: comprehensive HTML5 with minimum 600 words
- Explicit banned phrase list (delve, revolutionizing, groundbreaking, etc.)

### 4.4 Circuit Breaker Pattern

All external tool calls are wrapped by the `CircuitBreaker` class (`app/core/circuit_breaker.py:21`), which prevents cascading failures by short-circuiting calls to degraded services:

```
State Machine:

     ┌────────┐
     │ CLOSED │  ← Normal operation, calls pass through
     └───┬────┘
         │ Failure threshold exceeded (5 failures)
         ▼
     ┌────────┐
     │  OPEN  │  ← Calls immediately raise CircuitBreakerOpen
     └───┬────┘
         │ Recovery timeout elapsed (30s)
         ▼
     ┌───────────┐
     │ HALF_OPEN │  ← Allows limited probe calls (max 3)
     └───┬───────┘
         │
    ┌────┴────┐
    ▼         ▼
  Success   Failure
    │         │
    ▼         ▼
 ┌──────┐ ┌──────┐
 │CLOSED│ │ OPEN │
 └──────┘ └──────┘
```

**Configuration defaults:**
- `failure_threshold`: 5 consecutive failures before opening
- `recovery_timeout`: 30 seconds before transitioning to HALF_OPEN
- `half_open_max_retries`: 3 probe calls before closing again

The circuit breaker uses `asyncio.Lock` for thread-safe state transitions in the async context.

### 4.5 Rate Limiting

The `RateLimiterRegistry` (`app/core/rate_limiter.py:44`) implements token bucket rate limiting per model/service:

```python
class TokenBucket:
    capacity: int           # max burst size
    refill_rate: float      # tokens per second
    refill_interval: float  # 1.0 second granularity
```

When a bucket is exhausted, `ModelRateLimitError` is raised, which the orchestrator's retry logic catches and schedules for HEALING.

---

## 5. Agent Memory & State

GNONE agents are designed to be **stateless by default**. Each pipeline invocation is an isolated unit of work identified by a `correlation_id`. This design choice guarantees idempotency — replaying the same topic with the same brand voice produces identical output (modulo LLM nondeterminism).

### 5.1 AgentContext as Shared Memory

The `AgentContext` dataclass is the sole memory carrier across agents:

```python
@dataclass
class AgentContext:
    correlation_id: str        # UUID4, generated per pipeline run
    topic: str                 # from user request
    unified_truth_document: str  # written by ResearchAgent
    generated_content: dict    # written by CopywritingAgent
    critic_approved: bool      # written by CriticAgent
    refinement_cycles: int     # written by CriticAgent
    refinement_notes: str      # written by CriticAgent on failure
    brand_voice: str           # from user request
    errors: list[dict]         # appended by any agent
    metadata: dict             # catch-all for agent-specific data
```

The `set()` and `get()` methods allow flexible key-value access while maintaining backward compatibility with typed fields.

### 5.2 No Cross-Run Persistence

Agents retain zero state between pipeline invocations. This is intentional:
- **Idempotency**: Re-running a pipeline produces the same result
- **Horizontal scaling**: Any orchestrator instance can handle any request
- **Crash recovery**: A failed pipeline can be restarted from scratch without state reconciliation
- **Testing simplicity**: Each agent can be tested in isolation with a mock context

### 5.3 Session State in PostgreSQL

For the real-time meeting track (VoiceProxyAgent), state persistence is handled through the `proxy_sessions` table in PostgreSQL (`migrations/001_multi_tenant_schema.sql:149`):

```sql
CREATE TABLE proxy_sessions (
    id                  UUID PRIMARY KEY,
    client_id           UUID NOT NULL,
    agent_profile_id    UUID REFERENCES agent_profiles(id),
    recall_session_id   TEXT UNIQUE,
    livekit_room_name   TEXT,
    meeting_platform    TEXT NOT NULL,
    status              session_status NOT NULL DEFAULT 'PENDING_REVIEW',
    transcript_text     TEXT,
    transcript_summary  TEXT,
    revenue_closed      NUMERIC(12, 2) DEFAULT 0.00,
    deal_stage          TEXT DEFAULT 'discovery',
    ...
);
```

The session lifecycle: `PENDING_REVIEW → ACTIVE → COMPLETED | FAILED`

### 5.4 Vector Knowledge Retrieval

The `corporate_knowledge_vectors` table (backed by pgvector with HNSW index) enables real-time semantic retrieval during voice calls:

```
During an active meeting:
  1. Audio is transcribed in real-time
  2. Transcript chunks are embedded (1536-dim)
  3. Cosine similarity search against corporate_knowledge_vectors
  4. Top-5 results injected into agent context for informed responses
```

The `search_similar()` function (`app/services/vector_store.py:21`) performs <50ms ANN lookups using the HNSW index with `m=16, ef_construction=200`.

---

## 6. Real-Time Agent: VoiceProxyAgent

The VoiceProxyAgent is GNONE's most architecturally distinct agent. Unlike the batch-oriented content manufacturing pipeline, it operates in a real-time loop with sub-800ms latency requirements.

### 6.1 Architecture Stack

```
                    ┌──────────────────────────────────────┐
                    │         Zoom / Meet / Teams           │
                    └──────────────┬───────────────────────┘
                                   │ Meeting URL
                                   ▼
                    ┌──────────────────────────────────────┐
                    │       Recall.ai Container Manager     │
                    │  (Headless Chromium + Linux VM)       │
                    └──────────────┬───────────────────────┘
                                   │ WebRTC stream
                                   ▼
                    ┌──────────────────────────────────────┐
                    │        LiveKit Server Matrix          │
                    │  (WebRTC transport + tracks)          │
                    └──────────────┬───────────────────────┘
                                   │ Audio/Video frames
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VoiceProxyAgent Loop                           │
│                                                                  │
│  ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌─────────┐ │
│  │ Audio In │───►│  STT     │───►│ Gemini    │───►│  TTS    │ │
│  │ (16kHz)  │    │  Chunk   │    │  Reasoning│    │  Voice  │ │
│  └──────────┘    └───────────┘    └──────┬────┘    │  Clone  │ │
│                                          │         └────┬────┘ │
│                                          ▼              │      │
│                                   ┌──────────┐          │      │
│                                   │ pgvector │          │      │
│                                   │ RAG      │          │      │
│                                   └──────────┘          │      │
│                                                         ▼      │
│                                                    ┌──────────┐│
│                                                    │ Audio Out││
│                                                    │ (16kHz)  ││
│                                                    └──────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Key Design Decisions

**Model Target:** `gemini-2.5-flash-native-audio-preview`
- Native audio-in/audio-out over WebSockets (no separate STT/TTS pipeline required)
- Multi-modal frame processing: processes both audio samples and screen-share video frames concurrently
- Sub-800ms end-to-end latency for natural conversation flow

**Voice Clone Integration:**
- `agent_profiles` table stores `voice_clone_id` (ElevenLabs / Play.ht)
- Client-specific voice configuration per meeting
- `voice_speed` parameter configurable per profile (0.5x–2.0x)

**Interruption Handling:**
- Agent continuously monitors audio stream during its own speech
- If overlapping speech detected (human interrupts), agent immediately stops speaking
- Pauses listening for 500ms before re-engaging to avoid echo loops

**Screen-Share Tracking:**
- Video frames from the screen-share track are sampled at 1fps
- Frames are embedded and compared against the meeting transcript for context
- When a slide change is detected, the agent can verbally reference the new visual

### 6.3 WebSocket Transport

The `audio_stream` WebSocket endpoint (`app/routes/streaming.py:54`) handles bi-directional binary audio:

```python
@router.websocket("/ws/audio/{session_id}")
async def audio_stream(ws: WebSocket, session_id: str):
    await ws.accept()
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.receive" and message.get("bytes"):
            # Forward binary audio frames to LiveKit transport
            await ws.send_bytes(message["bytes"])
        elif message["type"] == "websocket.receive" and message.get("text"):
            # Handle JSON control messages (interruption, config, etc.)
            await ws.send_json(json.loads(message["text"]))
```

---

## 7. MCP (Model Context Protocol) Readiness

While GNONE does not yet implement the full MCP specification, the architecture is designed for pluggable model backends through a consistent service abstraction layer.

### 7.1 Service Abstraction Layer

Every model interaction flows through a service function that:
1. Constructs the API payload from domain parameters
2. Calls the external API via `httpx.AsyncClient`
3. Parses and validates the response through Pydantic models
4. Returns strongly typed domain objects (never raw JSON)

```python
# Pattern used by all services:
async def some_service(param: DomainType) -> DomainType:
    payload = build_payload(param)                  # step 1
    response = await httpx.post(endpoint, json=payload)  # step 2
    raw = parse_response(response)                  # step 3
    return DomainType.model_validate(raw)           # step 4
```

This means an agent like CopywritingAgent never knows whether it's calling GPT-4o, Llama 4, or a local model — it just calls `generate_platform_content(utd, brand_voice)`.

### 7.2 OpenRouter as Universal Router

OpenRouter provides a single API interface with model routing:

```python
settings.generator_model = "openai/gpt-oss-120b:free"  # copywriting
settings.critic_model = "nvidia/nemotron-3-super:free"  # critic
```

Swapping models requires changing only the config value — no agent code changes needed. This enables:
- **A/B testing**: route 10% of traffic to a new model for evaluation
- **Fallback chains**: if primary model is rate-limited, try secondary
- **Cost optimization**: use cheaper models for simpler tasks

### 7.3 Pluggable Backend Architecture

The config-driven model selection enables:

| Current Model | Swappable To | Use Case |
|-------------|-------------|----------|
| `gemini-3.1-flash-lite` | `claude-3.5-haiku`, `gemini-2.0-flash` | Research/grounding |
| `openai/gpt-oss-120b:free` | `llama-4-120b`, `gpt-4o-mini` | Content generation |
| `nvidia/nemotron-3-super:free` | `gpt-4o`, `claude-3.5-sonnet` | Critic/QA |
| `gemini-2.5-flash-native-audio` | `gpt-4o-audio-preview` | Voice/audio |

### 7.4 Tool Registration Pattern

GNONE's service layer effectively implements a tool registration pattern. Each tool is:
1. A standalone Python function in `app/services/`
2. Imported and called by exactly one agent
3. Wrapped by a circuit breaker for resilience
4. Tracked via OpenTelemetry spans and Prometheus metrics

To register a new tool:
1. Create `app/services/new_tool.py` with a single async function
2. Call it from the relevant agent's `execute()` method
3. Register it in `app/infrastructure/health.py` for health checking
4. Add latency histograms in `app/monitoring/prometheus.py`

---

## 8. Agent Observability

### 8.1 Correlation ID Propagation

Every pipeline invocation receives a UUID4 `correlation_id` at creation time (`app/core/orchestrator.py:25`). This ID is:

- Attached to every log line via structured JSON logging
- Passed through all OpenTelemetry spans as an attribute
- Included in error responses for debugging
- Stored in audit logs for post-hoc analysis

### 8.2 OpenTelemetry Tracing

The `setup_tracing()` function (`app/monitoring/traces.py:13`) configures OTLP export to a collector:

```python
def setup_tracing(service_name: str = "gnone-content-manufacturing"):
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"),
    )
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
        })
    )
```

**Span hierarchy per pipeline run:**
```
pipeline.run (root span)
├── research_agent.run
│   ├── gemini_grounding.research_topic  (HTTP call to Gemini API)
│   └── research_agent.execute
├── copywriting_agent.run
│   ├── openrouter_generator.generate    (HTTP call to OpenRouter)
│   └── copywriting_agent.execute
├── critic_agent.run
│   ├── critic_loop.call_critic          (HTTP call to OpenRouter)
│   ├── critic_loop.regenerate           (if rejected)
│   └── critic_agent.execute
└── moderator_agent.run
    └── moderator_agent.execute
```

### 8.3 Prometheus Metrics

The `MetricsRegistry` class (`app/core/metrics.py:54`) provides micrometer-style histograms and counters without requiring the Prometheus client library. Metrics are exported at `GET /api/v1/admin/metrics`.

**Per-agent metrics:**
- `gnone_requests_total{model, status}` — request count by model and status
- `gnone_{agent}_latency_seconds` — latency histogram per agent
- `gnone_critic_cycles_total{result}` — critic approval/rejection ratio
- `gnone_refinement_cycles` — distribution of critic refinement counts
- `gnone_errors_total{type}` — error count by error type

**Alert rules** (`app/monitoring/alerts.py`):
- CRITICAL: Error rate > 5% over 5 minutes
- CRITICAL: P95 latency > 120 seconds
- CRITICAL: Circuit breaker open for > 10 minutes
- WARNING: Critic rejection rate > 30% over 15 minutes
- WARNING: Token usage > 80% of daily quota

### 8.4 Structured Logging

The `JSONFormatter` (`app/core/logging_config.py:7`) outputs machine-parseable JSON logs:

```json
{
  "timestamp": "2026-05-19T14:30:00.123Z",
  "level": "INFO",
  "logger": "agent.critic_agent",
  "message": "Content approved on attempt 2",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 8.5 Grafana Dashboard

A pre-configured Grafana dashboard (`app/monitoring/dashboard.py`) visualizes:
- Pipeline latency (P50/P95/P99)
- Request & error rate timeseries
- Critic approval rate gauge
- Content distribution by platform
- Refinement cycle distribution heatmap
- Revenue tracking

---

## 9. Multi-Agent Failure Modes

### 9.1 Cascading Failure

**Problem:** An upstream agent (e.g., ResearchAgent) fails, causing all downstream agents (CopywritingAgent, CriticAgent, ModeratorAgent) to be skipped.

**Mitigation:**
- The orchestrator sets downstream nodes to SKIPPED status rather than FAILED
- This prevents wasted compute but gracefully degrades the pipeline
- The root cause is captured in `ctx.errors` with the originating agent and correlation ID

```
Failure Propagation:

ResearchAgent ──FAIL──► CopywritingAgent ──SKIP──► CriticAgent ──SKIP──► ModeratorAgent
```

### 9.2 Retry Storms

**Problem:** Under degraded API conditions, all agents enter HEALING simultaneously, causing exponential request amplification:

```
Time    Agent A    Agent B    Agent C    API Load
───     ───────    ───────    ───────    ────────
T+0s    FAIL       FAIL       FAIL       3 requests
T+1s    RETRY      RETRY      RETRY      6 requests
T+3s    RETRY      RETRY      RETRY      9 requests
T+6s    RETRY      RETRY      RETRY      12 requests
```

**Mitigation:**
- Each agent `max_retries` is capped at 3 (configurable in `AgentNode`)
- Linear backoff: `asyncio.sleep(1.0 * attempt_number)` prevents synchronized retry waves
- Circuit breaker opens after 5 consecutive failures, short-circuiting further retries
- The circuit breaker's HALF_OPEN state prevents immediate full recovery when the API comes back

### 9.3 Context Corruption

**Problem:** Malformed data is written to `AgentContext`, causing downstream agents to fail with confusing Pydantic validation errors.

**Example:**
```python
# CopywritingAgent writes malformed Twitter posts:
ctx.generated_content = {
    "twitter": {"posts": ["A" * 500]},  # exceeds 240 char limit
}
# CriticAgent then fails when validating CopywritingContract:
#   ValueError: Twitter post 1 exceeds 240 chars (500)
```

**Mitigation:**
- Pydantic validates every contract at agent boundaries
- `AgentContractViolation` includes the agent name and field that failed
- Downstream agents check for required fields before executing:

```python
# CopywritingAgent:17
if not ctx.unified_truth_document:
    raise ValueError("No Unified Truth Document available for copywriting.")
```

### 9.4 Contradictory Feedback (Generator vs Critic Oscillation)

**Problem:** The critic rejects content, the copywriter regenerates, the critic rejects again — potentially cycling indefinitely.

```
Cycle 1:  Copywriter ──► Critic ──(REJECT)──► notes
Cycle 2:  Copywriter ──► Critic ──(REJECT)──► notes
Cycle 3:  Copywriter ──► Critic ──(REJECT)──► MaxRetriesExceededError
```

**Mitigation:**
- `settings.max_retries` (default: 3) establishes a hard budget
- `MaxRetriesExceededError` captures the last refinement notes for debugging
- The pipeline returns best-effort content (last generation) rather than failing entirely
- The Grafana dashboard tracks refinement cycle distribution to identify problematic agents

### 9.5 Token Budget Exhaustion

**Problem:** Long critic cycles with full content regeneration consume excessive tokens (both input and output).

```
Cycle 1:  UTD (4000 tokens) + content (2000 tokens) = 6000 tokens
Cycle 2:  UTD (4000) + feedback (500) + content (2000) = 6500 tokens
Cycle 3:  UTD (4000) + feedback (1000) + content (2000) = 7000 tokens
Total:    19,500 tokens per pipeline run (3 cycles)
```

**Mitigation:**
- `response_format: {"type": "json_object"}` with `max_tokens: 4096` prevents runaway generation
- `max_token` limits configured per model in `Settings`
- Redis task queue deduplication prevents duplicate processing
- The critic's output is compressed via the `CRITIC_SYSTEM_PROMPT` which demands concise bullet-point feedback

---

## 10. Future Agent Architecture

### 10.1 Planned Specialized Agents

#### LegalReviewAgent
- **Role:** Scans generated content for regulatory compliance (GDPR, CCPA, SEC disclaimers)
- **Model Target:** `gpt-4o` or a fine-tuned legal LLM
- **Contract:** `LegalReviewContract` — `compliance_flags: list[ComplianceFlag]`, `required_disclaimers: list[str]`
- **Position:** Between CriticAgent and ModeratorAgent in the DAG

#### BrandVoiceAgent
- **Role:** Ensures cross-platform content consistency with client brand guidelines
- **Model Target:** Custom fine-tuned model or `claude-3.5-sonnet`
- **Contract:** `BrandVoiceContract` — `tone_score: float`, `vocabulary_deviations: list[str]`
- **Position:** Parallel to CriticAgent

#### CompetitiveAnalysisAgent
- **Role:** Analyzes competitor content and suggests differentiation angles
- **Model Target:** Gemini with googleSearch for competitive intelligence
- **Contract:** `CompetitiveAnalysisContract` — `competitor_mentions: list[str]`, `gap_opportunities: list[str]`
- **Position:** Parallel to ResearchAgent

### 10.2 Hierarchical Agent Coordination

The current flat DAG will evolve to support hierarchical supervision:

```
SupervisorAgent
├── Content Team
│   ├── ResearchAgent
│   ├── CopywritingAgent
│   ├── CriticAgent
│   └── LegalReviewAgent
├── Voice Team
│   ├── VoiceProxyAgent
│   ├── TranscriptAgent
│   └── SentimentAgent
└── Deployment Team
    ├── ModeratorAgent
    ├── SchedulingAgent
    └── AnalyticsAgent
```

The `SupervisorAgent` would:
1. Receive high-level tasks (e.g., "manufacture content for Q3 product launch")
2. Decompose into sub-tasks dispatched to team leads
3. Aggregate results, resolve conflicts, approve final output
4. Report status back to human operators

### 10.3 Agent Marketplace

A planned third-party plugin system where external agents implement a defined contract interface:

```python
# Future plugin contract interface
class AgentPlugin(ABC):
    @abstractmethod
    async def execute(self, ctx: AgentContext) -> AgentContext: ...
    
    @property
    @abstractmethod
    def contract_input(self) -> type[BaseModel]: ...
    
    @property
    @abstractmethod
    def contract_output(self) -> type[BaseModel]: ...
```

Third-party agents would be:
- Sandboxed via subinterpreters or container isolation
- Rate-limited by the platform's `TokenBucket`
- Monitored for cost and latency before appearing in the marketplace
- Discoverable via a registry with capability tags

### 10.4 Human-in-the-Loop Approval Gates

High-stakes content (financial disclaimers, medical claims, legal notices) will route through approval gates:

```
                    ┌──────────────────┐
                    │  Content Ready   │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │ Approval Gate    │
                    │ (risk score > 0.8)│
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
    ┌─────────────────┐          ┌─────────────────────┐
    │ Auto-Approve    │          │ Human Review Queue  │
    │ (low risk)      │          │ (email/slack alert) │
    └────────┬────────┘          └──────────┬──────────┘
             │                              │
             ▼                              ▼
    ┌─────────────────┐          ┌─────────────────────┐
    │ Deploy to       │          │ Approval/Rejection  │
    │ Platform Queue  │          │ within SLA (4 hrs)  │
    └─────────────────┘          └─────────────────────┘
```

Risk scoring would consider:
- Content domain (finance/healthcare → high risk)
- Critic confidence score (< 0.7 → high risk)
- Deployment target (blog → low risk, email → high risk)
- Client subscription tier (enterprise → higher review threshold)

### 10.5 Architecture Evolution Roadmap

```
Phase 1 (Current)        Phase 2 (Q3 2026)        Phase 3 (Q1 2027)
─────────────────        ────────────────        ─────────────────
Flat DAG                Hierarchical DAG         Multi-Orchestrator
5 agents                8-10 agents              15+ agents + plugins
Sequential execution    Parallel branches        Distributed execution
Single orchestrator     Supervisor agents         Agent mesh network
Manual config           Auto-scaling agents      Self-optimizing topology
```

---

## Appendix A: Key File Reference

| File | Purpose |
|------|---------|
| `app/core/orchestrator.py` | DAG engine, AgentContext, BaseAgent, AgentStatus |
| `app/agents/base.py` | Concrete base agent for all GNONE agents |
| `app/agents/research_agent.py` | Research & grounding via Gemini |
| `app/agents/copywriting_agent.py` | Multi-platform content generation |
| `app/agents/critic_agent.py` | Adversarial QA with self-healing loop |
| `app/agents/moderator_agent.py` | Content safety scanning (regex-based) |
| `app/agents/voice_agent.py` | Real-time voice proxy stub |
| `app/models/agent_contracts.py` | Pydantic contract models |
| `app/models/content_models.py` | MultiPlatformContent + validation |
| `app/services/gemini_grounding.py` | Gemini API + Google Search tool |
| `app/services/openrouter_generator.py` | OpenRouter API for copywriting |
| `app/services/critic_loop.py` | Critic verification + regeneration loop |
| `app/services/livekit_service.py` | LiveKit WebRTC room management |
| `app/services/vector_store.py` | pgvector ANN search client |
| `app/services/redis_queue.py` | Idempotent task queue |
| `app/core/circuit_breaker.py` | Circuit breaker pattern |
| `app/core/rate_limiter.py` | Token bucket rate limiter |
| `app/core/metrics.py` | Metrics registry + Prometheus export |
| `app/monitoring/traces.py` | OpenTelemetry tracing |
| `app/monitoring/prometheus.py` | Metric function definitions |
| `app/monitoring/dashboard.py` | Grafana dashboard JSON model |
| `app/monitoring/alerts.py` | Prometheus alert rules |
| `tests/unit/test_orchestrator.py` | DAG orchestrator unit tests |
| `tests/unit/test_agent_contracts.py` | Pydantic contract validation tests |
| `tests/unit/test_circuit_breaker.py` | Circuit breaker state machine tests |
| `tests/integration/test_content_pipeline.py` | Full pipeline integration tests |

---

## Appendix B: Communication Flow (Text-Based)

```
                   Pipeline: Content Manufacturing Request
                   ======================================

Client Request
     │
     │  POST /api/v1/manufacture
     │  { topic: "...", brand_voice_override: "..." }
     │
     ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Gateway                              │
│  app/routes/content_manufacturing.py                             │
│                                                                  │
│  1. Generate request_id (UUID4)                                  │
│  2. Set correlation_id = request_id                              │
│  3. Log: "Manufacturing content [id] for topic"                 │
│  4. Begin DAG pipeline                                           │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼  AgentContext(topic, brand_voice, correlation_id)
                   │
┌──────────────────────────────────────────────────────────────────┐
│  RESEARCH AGENT (gemini-3.1-flash-lite / googleSearch)           │
│                                                                  │
│  Input:  ctx.topic, ctx.brand_voice                              │
│  Action: research_topic(topic) → Gemini API + Google Search     │
│  Output: ctx.unified_truth_document, ctx.source_domains         │
│  Contract: ResearchContract validated                            │
│                                                                  │
│  UTD structure:                                                 │
│    • Factual paragraphs with inline source citations            │
│    • [UNVERIFIED] markers for unverified claims                 │
│    • Min 400 words, max 2000 words                              │
│    • Tracking fluff stripped from source pages                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼  ctx.unified_truth_document populated
                       │
┌──────────────────────────────────────────────────────────────────┐
│  COPYWRITING AGENT (openai/gpt-oss-120b:free / JSON mode)       │
│                                                                  │
│  Input:  ctx.unified_truth_document, ctx.brand_voice            │
│  Action: generate_platform_content(utd) → OpenRouter API        │
│  Output: ctx.generated_content (MultiPlatformContent dict)      │
│  Contract: CopywritingContract internally validated             │
│                                                                  │
│  Output structure (4 platforms):                                │
│    • twitter:  { posts: [5-10 strings ≤240 chars each] }        │
│    • linkedin: { body, hashtags }                               │
│    • facebook: { body, call_to_action }                         │
│    • blogspot: { title, seo_slug, meta_description, html_body } │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼  ctx.generated_content populated
                       │
┌──────────────────────────────────────────────────────────────────┐
│  CRITIC AGENT (nvidia/nemotron-3-super:free / JSON mode)        │
│                                                                  │
│  Input:  ctx.generated_content, ctx.unified_truth_document      │
│  Action: critic_verification_loop(content, utd)                 │
│                                                                  │
│  Loop (up to 3 iterations):                                     │
│    ┌─────────┐     ┌──────────┐     ┌──────────────┐          │
│    │ Call    │────►│ Evaluate │────►│ Approved?    │          │
│    │ Critic  │     │ Feedback │     │  ┌── YES ──► return     │
│    │ Model   │     │          │     │  └── NO  ──► regenerate │
│    └─────────┘     └──────────┘     └──────────────┘          │
│                                                                  │
│  Output: ctx.critic_approved (bool)                             │
│          ctx.refinement_cycles (int)                            │
│          ctx.refinement_notes (str, if rejected)                │
│          ctx.generated_content (possibly corrected)             │
│                                                                  │
│  Critic checks:                                                 │
│    • AI fluff hallmarks (delve, testament, etc.)               │
│    • Grammatical & layout issues                                │
│    • Structural completeness                                    │
│    • Brand voice drift                                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼  ctx.critic_approved = True/False
                       │
┌──────────────────────────────────────────────────────────────────┐
│  MODERATOR AGENT (rule-based regex scanning)                    │
│                                                                  │
│  Input:  ctx.generated_content (dict)                           │
│  Action: regex scan across all text content                     │
│                                                                  │
│  Scanned categories:                                            │
│    • Hate speech:   pattern: \b(hate|kill|destroy)...           │
│    • Harassment:    pattern: \b(bully|harass|threaten)...       │
│    • PII:           pattern: \b\d{3}[-.]?\d{3}[-.]?\d{4}\b     │
│    • Profanity:     pattern: \b(fuck|shit|asshole)...           │
│    • Competitor:    pattern: \b(competitor|rival|better than)   │
│    • Unverified:    pattern: \b(guaranteed|100%|best)           │
│                                                                  │
│  Output: ctx.metadata["moderator_verdict"] (ModeratorVerdict)   │
│                                                                  │
│  If flagged: content blocked, alert generated                   │
│  If clean:    content marked ready for deployment               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│  RESPONSE ASSEMBLY                                              │
│                                                                  │
│  Return: ContentResponse(                                       │
│      request_id=...,                                            │
│      topic=...,                                                 │
│      utd_summary=...,                                           │
│      generated_content=...,                                     │
│      critic_approved=...,                                       │
│      refinement_cycles=...,                                     │
│      created_at=...,                                            │
│  )                                                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Appendix C: Error Propagation Patterns

```
Pattern 1: Clean Success
─────────────────────────
research_agent ──SUCCESS──► copywriting_agent ──SUCCESS──► critic_agent ──SUCCESS──► moderator_agent ──SUCCESS──►
                              ↓                               ↓
                         ctx.unified_truth_document       ctx.critic_approved = True
                         ctx.generated_content            ctx.refinement_cycles = 1

Pattern 2: Critic Rejection with Self-Healing
──────────────────────────────────────────────
research_agent ──► copywriting_agent ──► critic_agent ──REJECT──► regenerate ──► critic_agent ──APPROVE──► moderator_agent
                                          ↓                       ↑
                                     refinement_notes        ctx.refinement_cycles = 2

Pattern 3: Upstream Failure with Downstream Skip
─────────────────────────────────────────────────
research_agent ──FAIL──► copywriting_agent ──SKIP──► critic_agent ──SKIP──► moderator_agent ──SKIP──►
     │
     ▼
ctx.errors = [{"agent": "research_agent", "error": "Gemini API timeout", "correlation_id": "..."}]

Pattern 4: Circuit Breaker Open
────────────────────────────────
research_agent ──► copywriting_agent ──FAIL (CircuitBreakerOpen)──► HEALING ──RETRY──► FAIL ──RETRY──► FAIL ──►
                                                                                                          │
                                                                                                     max_retries exhausted
                                                                                                          │
                                                                                                     ctx.errors appended
                                                                                                     downstream agents SKIPPED

Pattern 5: Retry Storm (Mitigated)
────────────────────────────────────
research_agent ──FAIL──► HEALING (sleep 1s) ──RETRY──► FAIL──► HEALING (sleep 2s) ──RETRY──► SUCCESS
copywriting ──FAIL──► HEALING (sleep 1s) ──RETRY──► FAIL──► HEALING (sleep 2s) ──RETRY──► SUCCESS
    │                              staggered timeouts due to linear backoff prevent simultaneous retry waves

Pattern 6: Token Budget Exhaustion
────────────────────────────────────
Cycle 1: Copywriter ──► Critic ──REJECT──► (token used: 6000)
Cycle 2: Copywriter ──► Critic ──REJECT──► (token used: 6500)
Cycle 3: Copywriter ──► Critic ──REJECT──► (token used: 7000)
         ↓
    MaxRetriesExceededError
         ↓
    Best-effort content returned with critic_approved=False
    ctx.refinement_notes = last critic's notes
```

---

*End of Report — GNONE Agent Systems Architecture v1.0.0*
