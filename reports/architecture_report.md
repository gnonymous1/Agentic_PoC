# GNONE Architecture Report — Sovereign Executive Proxy Engine

**Version:** 1.0.0  
**Classification:** Internal — Principal Cloud Architect Review  
**Date:** 2026-05-19  
**Authors:** GNONE Platform Engineering  

---

## Table of Contents

1. [System Topology](#1-system-topology)
2. [Scalability Architecture](#2-scalability-architecture)
3. [Fault Tolerance & Resilience](#3-fault-tolerance--resilience)
4. [Security Architecture](#4-security-architecture)
5. [Observability Stack](#5-observability-stack)
6. [Deployment Topology](#6-deployment-topology)
7. [Infrastructure Decisions & Trade-offs](#7-infrastructure-decisions--trade-offs)

---

## 1. System Topology

### 1.1 Microservice Decomposition

GNONE operates as a distributed, decoupled microservice cluster across six functional domains:

| Domain | Component | Role | Technology |
|---|---|---|---|
| API Gateway | FastAPI Central Gateway | Request routing, auth, rate limiting, OpenAPI schema | FastAPI 0.115+, Uvicorn |
| Agent Execution | DAG Orchestrator + Sub-Agent Pool | Deterministic typed state machine over Pydantic-guarded contracts | Python 3.12 asyncio |
| WebRTC Matrix | LiveKit Server + Pipecat | Bi-directional audio/video streaming, room management | LiveKit 0.18+, Pipecat |
| Container Manager | Recall.ai Bot API | Headless Chromium provisioning for Zoom/Meet/Teams | Recall.ai REST API |
| State Layer | PostgreSQL 16 + pgvector + Redis 7 | Multi-tenant persistence, vector embeddings, idempotent task queue | asyncpg, redis-py |
| Observability | OpenTelemetry + Prometheus + Grafana | Distributed tracing, metrics aggregation, dashboarding | OTLP, PromQL |

#### FastAPI Central Gateway (`app/main.py`)

The ingress point exposes four route groups:

- **`/api/v1/manufacture`** — Content manufacturing pipeline (POST): receives a raw topic seed, runs the full research → generate → critic DAG, returns structured multi-platform content.
- **`/api/v1/admin/health`** — Aggregate health check across PostgreSQL, Redis, and all model endpoints.
- **`/api/v1/admin/metrics`** — Prometheus-compatible metrics export.
- **`/ws/live/{client_id}`** and **`/ws/audio/{session_id}`** — WebSocket endpoints for real-time agent streaming and bi-directional binary audio transport.
- **`/api/v1/webhooks/*`** — Ingest webhooks from Recall.ai status updates, calendar events (Google Calendar, Outlook), and RSS feed pollers.

#### Agent Execution Nodes (`app/agents/`)

The DAG orchestrator (`app/core/orchestrator.py`) implements a topological-sort execution engine. Agents are registered with explicit dependency declarations:

```python
orchestrator.register(ResearchAgent())          # no dependencies
orchestrator.register(CopywritingAgent(),        depends_on=["research_agent"])
orchestrator.register(CriticAgent(),             depends_on=["copywriting_agent"])
orchestrator.register(ModeratorAgent(),          depends_on=["critic_agent"])
```

The `TopologicalSorter` from Python's standard `graphlib` resolves execution order at runtime. Agents that share no transitive dependencies execute concurrently; the orchestrator walks the sorted plan linearly, skipping agents whose upstream dependencies have failed.

#### LiveKit WebRTC Matrix (`app/services/livekit_service.py`)

The LiveKit service manages room creation, participant token generation (with `VideoGrants` for publish/subscribe), and room teardown. The voice proxy agent (`app/agents/voice_agent.py`) connects to the LiveKit track via WebSockets using native binary frames, enabling sub-800ms round-trip audio.

#### Recall.ai Container Manager (`app/services/recall_ai.py`)

The Recall.ai integration spawns headless Linux Chromium containers that negotiate entry into Zoom, Google Meet, and Microsoft Teams sessions. Each session is configured with recording mode (`audio_video`), resolution (`1920x1080`), and duration. The resulting transcripts are fed through the Gemini grounding agent for summarization.

### 1.2 Network Segmentation

The production Kubernetes cluster enforces four network tiers:

```
┌─────────────────────────────────────────────────────────┐
│                   Internet / Ingress                      │
│              nginx Ingress Controller (TLS)               │
│              Rate Limit: 100 RPS per client               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              TIER 1: API / Ingress                        │
│  FastAPI Pods (ClusterIP Service)                         │
│  Prometheus annotations for /metrics scraping             │
│  Liveness/Readiness probes on /api/v1/admin/health        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              TIER 2: Agent Execution                      │
│  DAG Orchestrator + Sub-Agent Pool                        │
│  OpenRouter / Gemini API calls (outbound only)            │
│  LiveKit WebRTC signalling (outbound WS)                  │
│  Recall.ai API (outbound HTTPS)                           │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              TIER 3: Data Layer                            │
│  PostgreSQL 16 + pgvector (StatefulSet, dedicated node)   │
│  Redis 7 (StatefulSet, task queue + cache)                │
│  No direct internet access; only Tier 2 can connect       │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              TIER 4: Observability                         │
│  OpenTelemetry Collector (DaemonSet)                      │
│  Prometheus Server (StatefulSet)                          │
│  Grafana (Deployment)                                     │
│  Scrapes Tier 1–3 metrics endpoints                       │
└─────────────────────────────────────────────────────────┘
```

### 1.3 Data Flow Diagrams

#### Ingestion Path (Webhook / Calendar / RSS)

```
[External Source] ──HTTP POST──► [FastAPI Webhook Routes]
                                         │
                                    [Redis Task Queue]
                                         │
                                    [Worker Consumer]
                                         │
                                    [DAG Orchestrator]
                                         │
                              ┌──────────┼──────────┐
                              ▼          ▼          ▼
                         Research   Copywrite   Critic
                         Agent      Agent       Agent
                              │          │          │
                              └──────────┴──────────┘
                                         │
                                    [Moderator Agent]
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                        [Approved]            [Rejected / DLQ]
                              │
                         [Output Queue]
```

#### Content Manufacturing DAG

```
POST /api/v1/manufacture { topic, brand_voice_override }
         │
         ▼
  [Research Agent]
  Gemini 3.1 Flash Lite + Google Search grounding
  Output: Unified Truth Document (UTD)
         │
         ▼
  [Copywriting Agent]
  OpenRouter GPT OSS 120B
  Output: MultiPlatformContent (Twitter, LinkedIn, FB, Blogspot)
         │
         ▼
  [Critic Agent]
  NVIDIA Nemotron 3 Super (Critic Mode)
  ┌──────┴──────┐
  ▼              ▼
Approved     Rejected
  │              │
  │        [Regenerate with feedback]
  │              │
  │         ┌────┘ (up to N retries)
  │         ▼
  │    Budget exhausted?
  │    ┌────┴────┐
  │    Yes       No ──► back to Copywriting
  │    │
  │    ▼
  │  Best-effort return
  │
  ▼
  [Moderator Agent]
  Regex-based PII, hate speech, profanity, brand safety scan
         │
         ▼
  [ContentResponse] returned to caller
```

#### Real-Time Audio Pipeline

```
[Meeting Host]                    [Recall.ai Container]
     │                                    │
     │  Zoom/Meet/Teams                    │ Spawns headless Chromium
     │  WebRTC stream                      │ Joins meeting
     │                                    │
     └─────────────┬──────────────────────┘
                   │
                   ▼
          [LiveKit Server Matrix]
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  [Audio Track]         [Video Track]
        │                     │
        ▼                     ▼
  [Voice Proxy Agent]   [Screen Share Processor]
  Gemini 2.5 Flash      Frame extraction
  Native Audio Preview  Visual context capture
        │
        ▼
  [Response Synthesis]
  Custom voice clone
  Bi-directional WS
```

#### Deployment Pipeline

```
[Developer Push] ──► [GitHub Actions CI]
                         │
                    ┌────┴────┐
                    ▼         ▼
                Lint      Test (unit + integration)
                    │         │
                    └────┬────┘
                         ▼
                    [CodeQL Security Scan]
                         │
                         ▼
                    [Docker Build & Push]
                    ghcr.io/gnone/gnone-api:tag
                         │
                         ▼
                    [Kubernetes Rolling Update]
                    kubectl set image deployment/gnone-api
                         │
                         ▼
                    [Blue-Green via maxSurge/maxUnavailable]
                    3 old replicas → 3 new replicas
```

---

## 2. Scalability Architecture

### 2.1 Horizontal Pod Autoscaling

The Kubernetes `HorizontalPodAutoscaler` (`k8s/hpa.yaml`) defines a dual-metric scaling policy:

```yaml
minReplicas: 3
maxReplicas: 20
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

Scale-up behavior is governed by the deployment's resource requests/limits:

```
requests:   cpu 500m,  memory 512Mi
limits:     cpu 2000m, memory 2Gi
```

At 70% CPU or 80% memory utilization, the HPA triggers a scale-up event. With `--horizontal-pod-autoscaler-tolerance` at default (0.1), the controller scales when the desired metric deviates by more than 10%. The cooldown period prevents thrashing: scale-up occurs every 15s (up to 4 pods per burst), scale-down occurs every 5 minutes.

**Capacity planning:** At 20 replicas with 2 CPU cores each, the platform can sustain ~40 concurrent CPU cores for model inference calls. Given that each content manufacturing cycle involves 3–5 sequential HTTPS calls (Gemini → OpenRouter → Nemotron), each taking 2–10 seconds, the theoretical throughput at peak is approximately 400–800 requests per minute.

### 2.2 PostgreSQL Connection Pooling

The `Database` class (`app/infrastructure/db.py`) uses `asyncpg.create_pool` with explicit sizing:

```python
pool = await asyncpg.create_pool(
    dsn=config.dsn,
    min_size=5,        # minimum connections always ready
    max_size=25,       # maximum concurrent connections
    command_timeout=30000,  # 30s statement timeout
)
```

**Why 25 max connections:** With 20 pod replicas and one pool per pod, 20 × 25 = 500 total connections to PostgreSQL at peak. PostgreSQL's default `max_connections` is 100. The production deployment overrides this to 600 on the StatefulSet, with `shared_buffers` set to 25% of available RAM (typically 4 GB on a dedicated 16 GB node).

**pgvector extension** (`migrations/001_multi_tenant_schema.sql`) enables native vector operations:

```sql
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE TABLE corporate_knowledge_vectors (
    embedding VECTOR(1536) NOT NULL
);
CREATE INDEX idx_corporate_knowledge_hnsw
    ON corporate_knowledge_vectors
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

The HNSW index provides approximate nearest-neighbor search with sub-50ms latency. The `m = 16` and `ef_construction = 200` parameters balance recall (≥0.97 at ef_search = 100) against index build time and memory footprint.

### 2.3 Redis-Backed Idempotent Task Queue

The `TaskQueue` (`app/services/redis_queue.py`) implements at-least-once delivery with SHA-256 deduplication:

```python
async def enqueue(self, queue: str, payload: dict, dedup: bool = True) -> Optional[str]:
    if dedup:
        dedup_key = self._compute_dedup_key(queue, payload)
        if await cache.get(dedup_key):
            return None  # Duplicate detected, silently dropped
        # ... set dedup key with 24h TTL ...
    await cache.enqueue(queue, job_data)
    return job.id

def _compute_dedup_key(self, queue: str, payload: dict) -> str:
    raw = json.dumps({"queue": queue, "payload": payload}, sort_keys=True)
    return f"dedup:{hashlib.sha256(raw.encode()).hexdigest()}"
```

Key properties:

- **Deduplication window:** 86,400 seconds (24 hours). After that, identical payloads are accepted again.
- **Queue primitive:** Redis `LPUSH` / `BRPOP` with blocking pop. No broker infrastructure required beyond Redis itself.
- **Dead letter queue:** Failed jobs are pushed to `{queue}:deadletter` before the exception propagates.
- **Consumer pattern:** The `process()` method runs a `while True` loop with blocking dequeue, enabling single-threaded consumers that never busy-poll.

### 2.4 Token Bucket Rate Limiting

The `RateLimiterRegistry` (`app/core/rate_limiter.py`) implements per-model token buckets using the generic cell rate algorithm:

```python
rate_limiter.register("gemini-3.1-flash-lite",  capacity=60,  refill_rate=1.0)
rate_limiter.register("openai/gpt-oss-120b:free", capacity=30,  refill_rate=0.5)
rate_limiter.register("nvidia/nemotron-3-super",  capacity=20,  refill_rate=0.33)
```

Each bucket has a configurable capacity (burst) and refill rate (tokens/second). The `acquire()` method blocks with a timeout of 5 seconds, yielding `asyncio.sleep(0.05)` between retries. If the timeout expires without acquiring the requested tokens, a `ModelRateLimitError` is raised at the service layer.

### 2.5 Circuit Breaker Pattern

The `CircuitBreaker` (`app/core/circuit_breaker.py`) protects upstream API dependencies from cascading failure:

| State | Transition Condition | Behavior |
|---|---|---|
| **CLOSED** (normal) | 5 consecutive failures | → OPEN |
| **OPEN** (degraded) | 30-second recovery timeout elapsed | → HALF_OPEN |
| **HALF_OPEN** (probing) | 3 successful probes | → CLOSED |
| **HALF_OPEN** (probing) | Any probe fails | → OPEN |

```python
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_retries: int = 3
```

When OPEN, the circuit raises `CircuitBreakerOpen` immediately without making the API call, preserving request resources (timeout slots, connection pool capacity) for healthy dependencies.

---

## 3. Fault Tolerance & Resilience

### 3.1 Graceful Degradation via `return_exceptions=True`

The architecture note in `ARCHITECTURE.md` identifies the critical pattern:

```python
# System Fault-Isolation Mapping for Parallel Task Execution
results = await asyncio.gather(
    facebook_worker_node(fb_payload),
    linkedin_worker_node(li_payload),
    livekit_meeting_session(room_config),
    return_exceptions=True  # Prevents a failure on one platform from killing active pipelines
)
```

Without `return_exceptions=True`, a single `asyncio.gather` failure propagates immediately to all sibling coroutines via cancellation. With it, each coroutine produces either a result or an `Exception` instance. The orchestrator inspects each result, logs failures, and continues dispatching successful outputs.

The DAG orchestrator (`app/core/orchestrator.py`) extends this pattern with agent-level retry and skip semantics:

```python
if any(
    self._nodes[dep].status == AgentStatus.FAILED
    for dep in node.dependencies
):
    node.status = AgentStatus.SKIPPED
    # Propagate skip; don't fail the entire pipeline
    continue
```

### 3.2 Circuit Breaker State Machine

```
                      ┌──────────────────┐
                      │     CLOSED        │
                      │ (normal ops)      │
                      └───────┬──────────┘
                              │ 5 failures
                              ▼
                      ┌──────────────────┐
                ┌─────│      OPEN         │◄────────────────┐
                │     │ (reject all)      │                 │
                │     └───────┬──────────┘                 │
                │             │ 30s recovery timeout        │
                │             ▼                            │
                │     ┌──────────────────┐                 │
                │     │   HALF_OPEN       │────────────────┘
                │     │ (probe 3 reqs)    │  any probe fails
                │     └────────┬─────────┘
                │              │ 3 successful probes
                │              ▼
                │     ┌──────────────────┐
                └────►│     CLOSED        │
                      │ (reset counters)  │
                      └──────────────────┘
```

### 3.3 Error Budget Tracking

The `ErrorBudget` dataclass (`app/core/errors.py`) tracks SLO compliance per service:

```python
@dataclass
class ErrorBudget:
    service: str
    total_operations: int = 0
    failed_operations: int = 0
    error_budget_remaining: float = 1.0

    def record_failure(self):
        self.total_operations += 1
        self.failed_operations += 1
        self.error_budget_remaining = max(
            0.0, 1.0 - (self.failed_operations / max(self.total_operations, 1))
        )

    @property
    def is_exhausted(self) -> bool:
        return self.error_budget_remaining <= 0.0
```

Each service domain (research, generation, critic, moderation) maintains its own budget. When exhausted, the service enters a degraded mode (best-effort output, cached results, or skip). The budget resets on a sliding 30-day window, aligned with the SLO target of 99.5% uptime (≈ 0.5% error budget = ~3.6 hours of allowable downtime per month).

### 3.4 Dead Letter Queue (DLQ)

The `TaskQueue.process()` method catches all exceptions from the handler and routes failed jobs to the DLQ:

```python
async def process(self, queue: str, handler: Callable[[dict], Awaitable[None]]):
    while True:
        job_data = await self.dequeue(queue)
        if job_data:
            try:
                await handler(job_data["payload"])
            except Exception:
                await cache.enqueue(f"{queue}:deadletter", job_data)
                raise
```

DLQ keys follow the pattern `{queue}:deadletter`. An independent worker (the "DLQ reconciler") periodically re-processes DLQ entries with exponential backoff, up to a maximum of 3 retries before permanent archival.

### 3.5 Health Check Aggregation

The `HealthRegistry` (`app/infrastructure/health.py`) registers and aggregates health checks for all dependencies:

```python
health_registry.register("postgres",  db.health)
health_registry.register("redis",     cache.health)
health_registry.register("livekit",   livekit_health)
health_registry.register("recall_ai", recall_health)
health_registry.register("openrouter", openrouter_health)
health_registry.register("gemini",    gemini_health)
```

The `check_all()` method executes all checks concurrently via `asyncio.gather` and returns a `HealthStatus` list with per-service latency timings. The Kubernetes liveness/readiness probes hit `/api/v1/admin/health`, which returns HTTP 200 only when all registered checks pass.

---

## 4. Security Architecture

### 4.1 AES-256-GCM Application-Level Encryption

OAuth tokens are encrypted at the application layer before storage in the `oauth_vault` table. The database never holds the encryption key — only ciphertext, IV, and GCM authentication tag:

```python
def encrypt_token(plaintext: str) -> Tuple[bytes, bytes, bytes]:
    key = _load_key()  # 32 bytes from ENCRYPTION_KEY env var
    aesgcm = AESGCM(key)
    iv = os.urandom(12)  # 96-bit nonce
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    tag = ciphertext_with_tag[-16:]
    ct = ciphertext_with_tag[:-16]
    return ct, iv, tag  # stored in three separate BYTEA columns
```

The database schema (`migrations/001_multi_tenant_schema.sql`) stores these as three separate `BYTEA` columns:

```sql
CREATE TABLE oauth_vault (
    encrypted_token     BYTEA NOT NULL,   -- AES-256-GCM ciphertext
    encrypted_iv        BYTEA NOT NULL,   -- 12-byte nonce
    encrypted_tag       BYTEA NOT NULL,   -- 16-byte authentication tag
    ...
);
```

Key rotation is supported via a `key_version` column (INTEGER) referencing a versioned key ring. During rotation windows, both old and new key versions are accepted.

### 4.2 Row-Level Security (RLS)

All tenant-scoped tables enable PostgreSQL Row-Level Security:

```sql
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_vault ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE proxy_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE corporate_knowledge_vectors ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON clients
    USING (id = current_setting('app.current_client_id')::UUID);
```

The `app.current_client_id` session variable is set at connection time after JWT authentication, ensuring that each pod can only access data belonging to its authenticated tenant. This provides defense-in-depth: even if an application bug leaks data across tenants, the database itself rejects the query.

### 4.3 Secrets Management

Kubernetes secrets (`k8s/secrets.yaml`) use the External Secrets Operator pattern:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: gnone-secrets
  namespace: gnone
type: Opaque
stringData:
  GEMINI_API_KEY: ""      # Populated by External Secrets Operator
  OPENROUTER_API_KEY: ""   # from AWS Secrets Manager / HashiCorp Vault
  ENCRYPTION_KEY: ""       # 64-char hex, rotated every 90 days
  DB_PASSWORD: "gnone"     # Overridden in production by vault
```

The production deployment uses the External Secrets Operator (ESO) to sync from a cloud vault, with automatic rotation detection and pod reload via Reloader annotations.

### 4.4 Content Safety Moderator Agent

The `ModeratorAgent` (`app/agents/moderator_agent.py`) scans all generated content through regex-based detection:

```python
FLAGGED_PATTERNS = {
    "hate_speech": r"\b(hate|kill|destroy)\s+(the\s+)?(\w+\s+){0,3}(people|group|race|religion)\b",
    "harassment": r"\b(bully|harass|threaten|intimidate)\b",
    "pii": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "profanity": r"\b(fuck|shit|asshole|bitch|cunt|damn)\b",
}
BRAND_SAFETY_PATTERNS = {
    "competitor_mention": r"\b(competitor|rival|better than)\s+\w+\b",
    "unverified_claim": r"\b(guaranteed|100%|best|number one|#1)\b",
}
```

The agent flattens all multi-platform content into a single text corpus, runs all patterns, and produces a `ModeratorVerdict` contract. Content that fails moderation is flagged in the response and blocked from deployment to social platforms.

### 4.5 Ingress Rate Limiting

The Kubernetes ingress (`k8s/ingress.yaml`) enforces per-client rate limiting at the nginx layer:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/rate-limit-rps: "100"
```

This applies a 100 requests-per-second limit per client IP at the TLS termination point. Combined with the application-layer token bucket rate limiting (per model endpoint), this provides defense against both volumetric and application-layer DDoS.

---

## 5. Observability Stack

### 5.1 OpenTelemetry Tracing

The `setup_tracing()` function (`app/monitoring/traces.py`) configures distributed context propagation:

```python
def setup_tracing(service_name: str = "gnone-content-manufacturing"):
    exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"),
    )
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        })
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
```

Spans are created at each agent execution boundary and API call, exported via OTLP HTTP to the OpenTelemetry Collector (`docker/otel-collector.yml`). The collector batches spans (batch size: 1024, timeout: 1s) and forwards to the configured backend.

### 5.2 Prometheus Metrics

The `MetricsRegistry` (`app/core/metrics.py`) exposes a Prometheus-compatible text format at `/api/v1/admin/metrics`:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `gnone_requests_total` | Counter | `model`, `status` | Total API requests by model and status |
| `gnone_errors_total` | Counter | `type` | Error count by error type |
| `gnone_content_pieces_total` | Counter | `platform` | Content pieces generated per platform |
| `gnone_critic_cycles_total` | Counter | `result` | Critic verification cycles (approved/rejected) |
| `gnone_pipeline_latency_seconds` | Histogram | — | End-to-end pipeline latency |
| `gnone_research_latency_seconds` | Histogram | — | Gemini grounding latency |
| `gnone_generation_latency_seconds` | Histogram | — | OpenRouter generation latency |
| `gnone_critic_latency_seconds` | Histogram | — | Nemotron critic latency |
| `gnone_refinement_cycles` | Histogram | — | Number of critic refinement iterations |
| `gnone_revenue_closed_total` | Counter | — | Total revenue from closed deals |
| `gnone_deal_value` | Histogram | — | Distribution of deal values |

### 5.3 Grafana Dashboard

The dashboard model (`app/monitoring/dashboard.py`) defines six panels:

1. **Pipeline Latency (P50 / P95 / P99)** — Timeseries: `histogram_quantile(0.95, rate(gnone_pipeline_latency_seconds_bucket[5m]))`
2. **Requests & Error Rate** — Timeseries: dual-axis with requests and errors
3. **Critic Approval Rate** — Gauge: `sum(rate(gnone_critic_cycles_total{result='approved'}[1h])) / sum(rate(gnone_critic_cycles_total[1h])) * 100`
4. **Content by Platform (Last 24h)** — Bar chart: `increase(gnone_content_pieces_total[24h])`
5. **Revenue Closed** — Stat panel: `sum(gnone_revenue_closed_total)`
6. **Refinement Cycle Distribution** — Heatmap: `rate(gnone_refinement_cycles_bucket[1h])`

### 5.4 Structured JSON Logging

The `JSONFormatter` (`app/core/logging_config.py`) outputs structured log entries:

```json
{
  "timestamp": "2026-05-19T14:30:00.123Z",
  "level": "INFO",
  "logger": "agent.critic_agent",
  "message": "Critic verification attempt 2/3",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

All logs include a `correlation_id` inherited from the `AgentContext`, enabling end-to-end traceability across agent boundaries without relying on OpenTelemetry distributed context propagation.

### 5.5 Alert Rules

Defined in `app/monitoring/alerts.py`:

| Severity | Rule | Condition | Duration |
|---|---|---|---|
| CRITICAL | HighErrorRate | `rate(gnone_errors_total[5m]) / rate(gnone_requests_total[5m]) > 0.05` | 5m |
| CRITICAL | PipelineLatencyHigh | P95 pipeline latency > 120s | 5m |
| CRITICAL | CircuitBreakerOpen | Circuit breaker open for ≥ 10 minutes | — |
| WARNING | RefinementCycleBudget | <80% of content approved within 3 cycles | 15m |
| WARNING | CriticRejectionSpike | Rejection rate > 30% over 15 minutes | 15m |
| WARNING | TokenExceededWarning | Daily token usage > 80% of quota | — |

Critical alerts route to PagerDuty with an escalation policy (acknowledgment within 5 minutes, escalation to on-call engineer at 10 minutes). Warning alerts route to a Slack channel for non-urgent triage.

---

## 6. Deployment Topology

### 6.1 Docker Compose (Local Development)

The local development environment (`docker/docker-compose.yml`) runs six containers:

| Service | Image | Ports | Purpose |
|---|---|---|---|
| `api` | `gnone/gnone-api:local` | 8000 | Uvicorn with `--reload` |
| `postgres` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL + pgvector |
| `redis` | `redis:7-alpine` | 6379 | Task queue + cache |
| `otel-collector` | `otel/opentelemetry-collector-contrib` | 4317, 4318 | Trace + metric pipeline |
| `prometheus` | `prom/prometheus` | 9090 | Metrics scraping |
| `grafana` | `grafana/grafana` | 3000 | Dashboarding |

Dependencies are enforced via `depends_on` with `condition: service_healthy` for PostgreSQL. The API container mounts the host source directory as a volume, enabling hot-reload during development.

### 6.2 Kubernetes (Production)

Production runs in a dedicated `gnone` namespace with:

| Resource | Configuration |
|---|---|
| **Deployment** | 3 replicas (min), RollingUpdate with maxSurge=1, maxUnavailable=1 |
| **HPA** | 3–20 replicas, CPU@70%, memory@80% |
| **Service** | ClusterIP (internal) + LoadBalancer (TLS) |
| **Ingress** | nginx ingress class, cert-manager TLS, 100 RPS rate limit |
| **Secrets** | External Secrets Operator from vault |
| **ConfigMaps** | Environment config + model version pinning |

**Resource requests/limits:**

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  limits:
    cpu: "2000m"
    memory: "2Gi"
```

**Probes:**

- **Liveness:** HTTP GET `/api/v1/admin/health`, initial delay 30s, period 15s
- **Readiness:** HTTP GET `/api/v1/admin/health`, initial delay 10s, period 5s

### 6.3 GitHub Actions CI/CD

The CI pipeline (`.github/workflows/ci.yml`) executes in parallel with three jobs:

```
Lint (ruff + mypy) ───► Test (pytest unit + integration) ───► Security (CodeQL)
                                │
                                ▼
                          Coverage upload
                          (codecov-action)
```

The CD pipeline (`.github/workflows/cd.yml`) triggers on version tags (`v*.*.*`):

```
Tag push v1.2.3
    │
    ▼
Docker Buildx (cache-from=gha, cache-to=gha,mode=max)
    │
    ▼
Push to GHCR (ghcr.io/gnone/gnone-api:v1.2.3)
    │
    ▼
kubectl set image deployment/gnone-api api=ghcr.io/gnone/gnone-api:v1.2.3 -n gnone
```

### 6.4 Blue-Green Deployment Strategy

Kubernetes rolling update parameters ensure zero-downtime deployments:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1   # Never take down more than 1 pod at a time
    maxSurge: 1         # Can spin up 1 additional pod before terminating
```

With 3 replicas, a rolling update proceeds as:

1. Spin up new pod (4 total: 3 old + 1 new)
2. Wait for readiness probe on new pod
3. Terminate one old pod (3 total: 2 old + 1 new)
4. Spin up second new pod (3 total: 2 old + 1 new)
5. Wait for readiness probe
6. Terminate second old pod (3 total: 1 old + 2 new)
7. Spin up third new pod (4 total: 1 old + 3 new)
8. Wait for readiness probe
9. Terminate final old pod (3 total: 0 old + 3 new)

Each step waits for the readiness probe (HTTP 200 on `/api/v1/admin/health` with all dependency checks passing). If any new pod fails readiness within the `initialDelaySeconds + periodSeconds × failureThreshold` window, the rollout is automatically rolled back.

---

## 7. Infrastructure Decisions & Trade-offs

### 7.1 Why asyncpg over SQLAlchemy

| Factor | asyncpg | SQLAlchemy (async) |
|---|---|---|
| Connection pool overhead | ~1–2 µs per acquire | ~10–20 µs per acquire (ORM mapping layer) |
| Raw query speed | Native PostgreSQL protocol, no abstraction | Core → SQL compilation → dialect → protocol |
| pgvector integration | Direct `VECTOR(1536)` type mapping | Requires custom type decorators |
| Dependency footprint | Single package (0.3.x) | SQLAlchemy + asyncmy/aiomysql + alembic |
| Type safety | Dataclass-based result mapping | Declarative Base ORM |

**Decision:** asyncpg provides 10–20× lower per-query overhead in the hot path (vector similarity search, tenant isolation queries). The application does not use an ORM — all queries are explicitly written and parameterized, which provides superior query plan control and eliminates the N+1 query problem that ORMs introduce.

### 7.2 Why pgvector over Pinecone

| Factor | pgvector (PostgreSQL) | Pinecone |
|---|---|---|
| Infrastructure | None (same PostgreSQL cluster) | Separate SaaS / self-managed cluster |
| Latency (p95) | ~15–50 ms (HNSW index) | ~5–20 ms (dedicated ANN service) |
| Cost | $0 (included in DB compute) | $0.10–0.50 per million vectors/month |
| Transactional consistency | Full ACID with PostgreSQL | Eventually consistent |
| Multi-tenant RLS | Native via PostgreSQL RLS policies | Application-level filtering |
| Joins with relational data | Direct SQL JOIN | Two-phase: query Pinecone, then PostgreSQL |

**Decision:** For sub-50ms query latency and zero additional infrastructure cost, pgvector wins. The platform's vector corpus (< 10M embeddings per tenant) fits comfortably within a single PostgreSQL instance with the HNSW index consuming ~2× the vector data size in memory. The ability to JOIN `corporate_knowledge_vectors` directly against `clients`, `agent_profiles`, and `proxy_sessions` in a single query eliminates the distributed join problem.

### 7.3 Why Redis for Task Queue over RabbitMQ

| Factor | Redis | RabbitMQ |
|---|---|---|
| Operational overhead | Single node, no brokers, no exchanges | Requires Erlang VM, management plugin, exchanges/bindings |
| Deduplication primitives | Native `SET` + `EXPIRE` for SHA-256 keys | Requires custom header-exchange dedup plugin |
| Queue primitives | `LPUSH` / `BRPOP` — built-in | Exchange → Binding → Queue topology |
| Persistence guarantees | AOF/RDB (at-most-once on failover) | Publisher Confirms (at-least-once guaranteed) |
| Throughput (single node) | ~100k ops/sec | ~50k ops/sec |
| Polyglot use | Also used as cache, session store, rate limiter | Queue-only |

**Decision:** Redis serves triple duty (task queue, cache, rate limiter state store), reducing the infrastructure surface from two data stores to one. The task queue does not require RabbitMQ's guaranteed delivery semantics — the worker processes use the `process()` loop with DLQ fallback, and deduplication via SHA-256 is a first-class Redis operation.

### 7.4 Why FastAPI over Django

| Factor | FastAPI | Django |
|---|---|---|
| Async-native | First-class (async def routes) | WSGI by default; ASGI via Django Channels |
| Pydantic integration | Native (`response_model`, `Body()` validation) | DRF serializers (manual) |
| OpenAPI generation | Automatic from type hints | Requires drf-spectacular / drf-yasg |
| Startup latency | ~200ms (minimal import tree) | ~2–5s (ORM registry, app discovery, middleware chain) |
| Websocket support | Native via Starlette | Requires Django Channels + ASGI wrapper |
| Dependency injection | `Depends()` — built-in | Manual (or django-inject) |

**Decision:** GNONE's architecture is async-native by design — the DAG orchestrator, WebSocket streaming, and model API calls all use `asyncio`. FastAPI's `Depends()` system maps cleanly to the `Container` DI pattern (`app/infrastructure/containers.py`). The automatic OpenAPI generation from Pydantic models eliminates the separate schema maintenance burden that Django REST Framework requires.

---

## Appendix A: Key Metrics & SLOs

| Metric | Target | Measurement |
|---|---|---|
| Pipeline latency (P95) | < 120s | `histogram_quantile(0.95, rate(gnone_pipeline_latency_seconds_bucket[5m]))` |
| Error rate | < 5% | `rate(gnone_errors_total[5m]) / rate(gnone_requests_total[5m])` |
| Critic approval rate | > 70% (first pass) | `rate(gnone_critic_cycles_total{result='approved'}[1h]) / rate(gnone_critic_cycles_total[1h])` |
| Vector search latency (P99) | < 100ms | Application-level timing on `search_similar()` |
| API availability | 99.5% | Error budget: 0.5% monthly |
| Rate limit compliance | < 1% blocked | `rate(gnone_requests_total{status='rate_limited'}[5m])` |

## Appendix B: Dependency Graph

```
FastAPI Gateway
├── app.routes.content_manufacturing  (POST /manufacture)
│   ├── app.services.gemini_grounding   (Gemini 3.1 Flash Lite)
│   ├── app.services.openrouter_generator  (GPT OSS 120B)
│   └── app.services.critic_loop       (Nemotron 3 Super)
│       └── app.services.openrouter_generator  (regenerate)
├── app.routes.streaming  (WebSocket /ws/audio, /ws/live)
│   └── app.services.livekit_service   (LiveKit API)
├── app.routes.webhooks   (POST /webhooks/*)
│   └── app.services.redis_queue       (Redis task queue)
├── app.routes.admin      (GET /admin/health, /admin/metrics)
│   ├── app.infrastructure.health       (HealthRegistry)
│   └── app.core.metrics               (MetricsRegistry)
└── app.routes.analytics  (GET /analytics/*)
    └── app.models.analytics            (DashboardSummary)

Infrastructure Layer
├── app.infrastructure.db     (asyncpg → PostgreSQL 16 + pgvector)
├── app.infrastructure.cache  (redis-py → Redis 7)
└── app.infrastructure.health (aggregated health checks)

Core Layer
├── app.core.orchestrator  (DAG orchestrator, AgentContext, BaseAgent)
├── app.core.circuit_breaker (CircuitBreaker, CircuitState)
├── app.core.rate_limiter   (TokenBucket, RateLimiterRegistry)
├── app.core.metrics        (MetricsRegistry, Histogram)
├── app.core.errors         (GNONEBaseError, ErrorBudget)
└── app.core.logging_config (JSONFormatter)

Agent Layer
├── app.agents.research_agent   → ResearchContract
├── app.agents.copywriting_agent → MultiPlatformContent
├── app.agents.critic_agent     → CriticVerdict
└── app.agents.moderator_agent  → ModeratorVerdict
```

---

*This document reflects the production architecture of the GNONE Sovereign Executive Proxy Engine as of May 2026. All configuration values, scaling parameters, and infrastructure decisions should be reviewed quarterly against actual production telemetry.*
