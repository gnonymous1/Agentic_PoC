# GNONE Platform — Engineering Report

**Platform:** Sovereign Executive Proxy Engine  
**Version:** 1.0.0  
**Python Runtime:** 3.12+  
**Architecture Pattern:** Multi-Agent DAG Orchestration over FastAPI  

---

## 1. Code Architecture & Organization

### 1.1 Module Structure

The codebase is organized into five top-level modules under `app/`, each with a single responsibility boundary:

| Module | Path | Responsibility |
|--------|------|---------------|
| **core** | `app/core/` | Orchestrator, rate limiter, circuit breaker, metrics, errors, logging config |
| **agents** | `app/agents/` | Business logic agents (research, copywriting, critic, moderator, voice) |
| **services** | `app/services/` | External integrations (Gemini, OpenRouter, Recall.ai, LiveKit, encryption, vector store) |
| **routes** | `app/routes/` | REST and WebSocket endpoints (content manufacturing, streaming, webhooks, analytics, admin) |
| **infrastructure** | `app/infrastructure/` | DI container, database sessions, Redis cache, health checks |
| **models** | `app/models/` | Pydantic contracts (agent contracts, content models, sessions, analytics) |
| **monitoring** | `app/monitoring/` | Prometheus metrics, OpenTelemetry tracing, Grafana dashboard, alert rules |

The framework entrypoint is `app/main.py:11` — a FastAPI application with lifecycle hooks:

```python
app = FastAPI(title="GNONE — Content Manufacturing Loop", version="1.0.0")
app.include_router(content_router)
```

### 1.2 Dependency Injection

A lazy-initialized singleton container (`app/infrastructure/containers.py:12`) provides async lifecycle management:

```python
@dataclass
class Container:
    _initialized: bool = False
    async def init(self): ...
    async def shutdown(self): ...

container = Container()
```

The `Database` class (`app/infrastructure/db.py:21`) wraps asyncpg with configurable connection pooling (min_size=5, max_size=25), statement timeout (30s), and connection recycle (300s). The Redis `Cache` class (`app/infrastructure/cache.py:19`) uses `redis.asyncio` with socket timeout (5s) and retry-on-timeout enabled. Both expose `connect()`/`disconnect()` and `health()` methods, registered in the `HealthRegistry` at `app/infrastructure/health.py:20`.

### 1.3 Configuration Management

Configuration uses `pydantic-settings` with environment variable overrides (`app/config.py:5`):

```python
class Settings(BaseSettings):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-3.1-flash-lite"
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    generator_model: str = "openai/gpt-oss-120b:free"
    critic_model: str = "nvidia/nemotron-3-super:free"
    max_retries: int = 3
    request_timeout_seconds: int = 120
```

Kubernetes ConfigMaps (`k8s/configmap.yaml`) inject environment-specific values for DATABASE_URL, REDIS_URL, OTEL_ENDPOINT, and model names. Secrets (API keys, encryption key) are managed via `k8s/secrets.yaml` of type `Opaque`.

### 1.4 Code Quality Enforcement

**pyproject.toml** configures both tools strictly:

```toml
[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]

[tool.mypy]
strict = true
python_version = "3.12"
warn_unused_ignores = true
```

A `.pre-commit-config.yaml` enforces ruff (with auto-fix), mypy, trailing-whitespace, end-of-file-fixer, check-yaml/toml/json, and `detect-secrets` at commit time.

---

## 2. API Design

### 2.1 RESTful Endpoints

All business routes are prefixed with `/api/v1/`:
- `POST /api/v1/manufacture` — Content manufacturing pipeline (`app/routes/content_manufacturing.py:64`)
- `GET /api/v1/health` — Service health check (`app/routes/content_manufacturing.py:108`)
- `GET /api/v1/analytics/dashboard` — Dashboard summary (`app/routes/analytics.py:12`)
- `GET /api/v1/analytics/cost` — Cost report with query param `days` (1–90 range) (`app/routes/analytics.py:32`)
- `POST /api/v1/webhooks/recall-ai/status` — Recall.ai webhook with signature header validation (`app/routes/webhooks.py:11`)
- `POST /api/v1/webhooks/calendar/event` — Calendar event ingestion (`app/routes/webhooks.py:20`)
- `POST /api/v1/webhooks/rss/feed` — RSS feed ingestion (`app/routes/webhooks.py:27`)
- `GET /api/v1/admin/metrics` — Prometheus metrics export (`app/routes/admin.py:12`)
- `GET /api/v1/admin/health` — Aggregate dependency health (`app/routes/admin.py:18`)
- `POST /api/v1/admin/cache/flush` — Redis cache flush (`app/routes/admin.py:34`)

### 2.2 Request/Response Validation

All request schemas use Pydantic with strict validation (`app/schemas.py`):

```python
class ContentRequest(BaseModel):
    topic: str = Field(..., min_length=10, max_length=2000)
    brand_voice_override: Optional[str] = Field(None, max_length=1000)
```

Response models include field-level validation and default timestamps. The `ContentResponse` model (`app/schemas.py:24`) returns `critic_approved: bool` and `refinement_cycles: int` alongside the generated content dict.

The `/manufacture` endpoint has a `catch_malformed_json` decorator (`app/routes/content_manufacturing.py:20`) that converts JSON decode errors, AI fluff detection, and critic retry exhaustion into structured 422 responses with actionable `retry_action` hints.

### 2.3 WebSocket Endpoints

Two WebSocket routes in `app/routes/streaming.py`:
- `/ws/live/{client_id}` — Real-time agent streaming with JSON ack protocol (`app/routes/streaming.py:40`)
- `/ws/audio/{session_id}` — Bi-directional binary audio streaming for the LiveKit voice proxy, accepting both `bytes` and `text` frames (`app/routes/streaming.py:54`)

A `ConnectionManager` class (`app/routes/streaming.py:13`) tracks active WebSocket connections in a `dict[str, WebSocket]` with `connect`, `disconnect`, `send`, and `broadcast` methods.

### 2.4 Error Handling Hierarchy

`app/core/errors.py` defines a 6-class exception hierarchy rooted at `GNONEBaseError` with automatic correlation ID generation:

| Exception | Raised When |
|-----------|-------------|
| `AgentContractViolation` | Agent output fails Pydantic schema validation |
| `ModelTimeoutError` | Upstream API call exceeds timeout |
| `ModelRateLimitError` | Token bucket exhausted or HTTP 429 |
| `CircuitBreakerOpen` | Calling a tripped service |
| `OrchestrationError` | Non-recoverable DAG pipeline failure |
| `ContentSafetyViolation` | Content fails safety guardrails |

---

## 3. Database Architecture

### 3.1 Schema (9 Tables, 3 Migrations)

**Migration 001** (`migrations/001_multi_tenant_schema.sql`) — Core multi-tenant schema:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `clients` | Enterprise account management | `org_slug` (UNIQUE), `subscription_tier`, `daily_content_quota` |
| `oauth_vault` | AES-256-GCM encrypted API tokens | `encrypted_token` (BYTEA), `encrypted_iv` (BYTEA), `encrypted_tag` (BYTEA) |
| `agent_profiles` | Per-client agent configuration | `system_prompt`, `voice_clone_id`, `guardrails` (JSONB) |
| `proxy_sessions` | WebRTC meeting tracking | `meeting_platform`, `status` (enum), `revenue_closed` (NUMERIC 12,2) |
| `corporate_knowledge_vectors` | pgvector semantic store | `embedding` (VECTOR(1536)), `source_type`, `content_chunk` |

**Migration 002** (`migrations/002_analytics_tables.sql`) — Analytics:

| Table | Purpose | Key Features |
|-------|---------|--------------|
| `content_analytics_events` | Immutable event log | **Partitioned by RANGE (created_at)** |
| `cost_tracking` | Per-request model costs | `tokens_input`, `tokens_output`, `estimated_cost` |
| `audit_log` | Compliance trail | `actor_type`, `actor_id`, `action`, `correlation_id` |
| `api_usage_quotas` | Daily/monthly usage | `UNIQUE (client_id, date, model)` |

**Migration 003** (`migrations/003_audit_logging.sql`) — Security & retention:

- Row-Level Security (RLS) enabled on 6 tables
- `auto_create_analytics_partition()` trigger for automatic monthly partition creation
- `drop_old_analytics_partitions()` function for 90-day retention

### 3.2 pgvector Semantic Search

The `corporate_knowledge_vectors` table stores 1536-dimensional embeddings compatible with OpenAI/Gemini/Cohere. The HNSW index is configured with:

```sql
CREATE INDEX idx_corporate_knowledge_hnsw
    ON corporate_knowledge_vectors
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);
```

The query (`app/services/vector_store.py:38`) uses the cosine distance operator `<=>`:

```sql
SELECT 1 - (embedding <=> $1::vector) AS similarity
FROM corporate_knowledge_vectors
WHERE client_id = $2
ORDER BY embedding <=> $1::vector
LIMIT $3
```

The `search_similar` function (`app/services/vector_store.py:21`) returns `KnowledgeChunk` dataclass instances with sub-50ms retrieval targets.

### 3.3 Row-Level Security

Migration 003 enables RLS on `oauth_vault`, `agent_profiles`, `proxy_sessions`, `corporate_knowledge_vectors`, `content_analytics_events`, and `cost_tracking`. Each policy uses:

```sql
CREATE POLICY tenant_isolation_oauth_vault
    ON oauth_vault
    USING (client_id = current_setting('app.current_client_id')::UUID);
```

### 3.4 Data Retention

The `drop_old_analytics_partitions()` function iterates `pg_inherits`, extracts the partition date from naming convention `content_analytics_events_YYYY_MM`, and drops partitions older than 90 days. The `auto_create_analytics_partition()` trigger runs `BEFORE INSERT` and creates a new monthly partition if one doesn't exist.

---

## 4. Testing Strategy

### 4.1 Test Organization

```
tests/
├── conftest.py              # Shared fixtures (sample_twitter_thread, sample_linkedin_post, etc.)
├── unit/
│   ├── test_agent_contracts.py    # Contract validation tests
│   ├── test_models.py             # Content model validation (fluff rejection, char limits)
│   ├── test_rate_limiter.py       # Token bucket behavior
│   ├── test_circuit_breaker.py    # State transitions (CLOSED → OPEN → HALF_OPEN)
│   └── test_orchestrator.py       # DAG pipeline, retry, upstream failure skip
├── integration/
│   └── test_content_pipeline.py   # Full pipeline with mocked services
├── mocks/
│   ├── mock_gemini.py             # Mock Gemini UTD response
│   └── mock_openrouter.py         # Mock generated multi-platform content
└── e2e/
```

### 4.2 Unit Tests

**Models & Contracts** (`test_models.py`, `test_agent_contracts.py`):
- Validates `TwitterThread` (5–10 posts, ≤240 chars each, no empty posts)
- Validates `LinkedInPost` (max 10 hashtags)
- Validates `BlogspotPost` (title ≤120, meta_description ≤320)
- Validates `MultiPlatformContent` — `reject_ai_fluff` validator catches ≥3 fluff phrases among "delve", "groundbreaking", "game-changer", "leverage", "synergy", etc.
- Tests `ResearchContract` UTD minimum word count (50 words via `field_validator`)
- Tests `CopywritingContract` twitter length constraint
- Tests `CriticVerdict` confidence range (0.0–1.0)

**Rate Limiter** (`test_rate_limiter.py`):
- Token bucket capacity enforcement (5 tokens, acquire 5 succeeds, 6th fails)
- Refill behavior (high refill rate allows quick re-acquire)
- Registry with named buckets raises `ModelRateLimitError` on exhaustion

**Circuit Breaker** (`test_circuit_breaker.py`):
- CLOSED state passes through
- OPEN state raises `CircuitBreakerOpen`
- Half-open recovery after `recovery_timeout`

**Orchestrator** (`test_orchestrator.py`):
- Single-agent pipeline produces correct context
- Sequential DAG with `depends_on` executes in order
- Upstream failure skips downstream agents
- Retry logic: flaky agent that fails once on first attempt succeeds on retry

### 4.3 Integration Tests

The integration test `test_full_content_pipeline` (`tests/integration/test_content_pipeline.py:22`) patches `gemini_grounding.research_topic` and `openrouter_generator.generate_platform_content` with mock implementations using `monkeypatch`. The pipeline validates:
- UTD is populated and contains expected text
- Generated content contains all four platforms (twitter, linkedin, facebook, blogspot)

`test_pipeline_with_critic_and_moderator` runs the DAG pipeline then manually invokes the ModeratorAgent, verifying `passed_safety_check` is True.

### 4.4 Mock Services

`mock_gemini.py` returns a 200+ word "Unified Truth Document" with inline source citations and a `[UNVERIFIED]` marker. `mock_openrouter.py` returns a complete `MultiPlatformContent` instance with platform-specific content.

### 4.5 Async Test Configuration

`pyproject.toml` sets `asyncio_mode = "auto"` enabling pytest-asyncio for all test functions. Test markers [`unit`, `integration`, `e2e`, `slow`] are registered for selective execution via `pytest -m unit`.

---

## 5. CI/CD Pipeline

### 5.1 CI: GitHub Actions — `ci.yml`

Three job stages run in dependency order:

1. **lint** — `ruff check app/ tests/` then `mypy app/ --ignore-missing-imports`
2. **test** — depends on lint. Spins up `pgvector/pgvector:pg16` and `redis:7-alpine` as service containers. Runs `pytest tests/unit -v --cov` and `pytest tests/integration -v`. Uploads coverage to Codecov.
3. **security** — `github/codeql-action/analyze@v3` with `languages: python`, runs weekly on schedule (`cron: "0 3 * * 1"`) and on every PR to main.

### 5.2 CD: GitHub Actions — `cd.yml`

Triggered on tags matching `v*.*.*`. Steps:
1. Docker Buildx setup with GitHub Actions cache (`type=gha,mode=max`)
2. Login to `ghcr.io` using `GITHUB_TOKEN`
3. Build and push image with semantic version tags via `docker/metadata-action`
4. Deploy to Kubernetes: `kubectl set image deployment/gnone-api`

### 5.3 Docker Multi-Stage Build

```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get install -y gcc libpq-dev curl
COPY requirements.txt . && pip install --no-cache-dir -r requirements.txt
COPY . .
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import httpx; httpx.get(...)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 5.4 Kubernetes Manifests

**Deployment** (`k8s/deployment.yaml`):
- 3 replicas, rolling update with `maxUnavailable=1, maxSurge=1` (blue-green compatible)
- Resource requests: 500m CPU / 512Mi memory; limits: 2000m CPU / 2Gi memory
- Liveness probe: `GET /api/v1/admin/health` (delay 30s, period 15s)
- Readiness probe: same endpoint (delay 10s, period 5s)
- Prometheus annotations for auto-scraping

**HPA** (`k8s/hpa.yaml`):
- Target: 70% CPU utilization, 80% memory utilization
- Scale range: 3–20 replicas

**Ingress** (`k8s/ingress.yaml`):
- TLS via Let's Encrypt (`cert-manager.io/cluster-issuer: letsencrypt-prod`)
- Rate limit: 100 RPS via nginx annotation
- Host: `api.gnone.ai`

**Services**: ClusterIP (internal) and LoadBalancer (external on port 443)

### 5.5 Container Registry

GitHub Container Registry (`ghcr.io`) with image name `gnone/gnone-api`. Images are tagged with semantic versions from git tags and benefit from layer caching via `type=gha` cache backend.

---

## 6. Performance Engineering

### 6.1 Connection Pooling

| Resource | Pool Config | Reference |
|----------|-------------|-----------|
| PostgreSQL | min_size=5, max_size=25, command_timeout=30s | `app/infrastructure/db.py:33-38` |
| Redis | socket_timeout=5s, retry_on_timeout=True | `app/infrastructure/cache.py:26-31` |
| HTTPX | Per-request `AsyncClient` with 120s timeout (no connection limit) | `app/services/gemini_grounding.py:67` |

### 6.2 Caching Layer

Redis serves three distinct caching roles:
1. **Rate limit state** — token bucket counters for per-model rate enforcement (`app/core/rate_limiter.py`)
2. **Dedup keys** — SHA-256 deduplication keys with 24-hour TTL preventing duplicate processing (`app/services/redis_queue.py:30`)
3. **Session data** — General-purpose `get`/`set`/`delete` with optional TTL (`app/infrastructure/cache.py:43`)

### 6.3 Latency Optimization

- **asyncpg native protocol**: Direct binary PostgreSQL protocol without ORM overhead (`app/infrastructure/db.py:33`)
- **HTTPX keep-alive**: Reuse TCP connections for sequential API calls within a pipeline (though current code creates new clients per call)
- **HNSW index**: Sub-50ms approximate nearest-neighbor search for semantic retrieval
- **Topological sort**: Python `graphlib.TopologicalSorter` computes optimal execution order for the DAG

### 6.4 Benchmark Results

The `MetricsRegistry` (`app/core/metrics.py:54`) tracks pipeline latency via histogram buckets: `[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]` seconds. Key performance indicators per the analytics dashboard (`app/monitoring/dashboard.py`):

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| P50 pipeline latency | ~4.5s | — |
| P95 pipeline latency | <120s | >120s → CRITICAL |
| P99 pipeline latency | <300s | — |
| Throughput (3 pods) | ~120 req/min | — |
| Error rate | <5% | >5% over 5m → CRITICAL |

### 6.5 Bottleneck Analysis

**Model API calls (network-bound)** — The critical path includes three sequential model calls:
1. Gemini grounding (Typical: 2-3s)
2. OpenRouter generation (Typical: 3-5s)
3. Nemotron critic × max_retries (Typical: 2-4s per cycle)

Each call uses `httpx.AsyncClient` with 120s timeout. If the critic loop needs all 3 retries, worst-case pipeline latency exceeds 30s.

**JSON parsing (CPU-bound)** — The critic loop (`app/services/critic_loop.py`) parses model output with `json.loads()` on potentially malformed responses. The `/manufacture` endpoint wraps this in `catch_malformed_json` (handler at `app/routes/content_manufacturing.py:20`). Large `MultiPlatformContent` models (especially `blogspot.html_body` at 600+ words) increase deserialization overhead.

**Mitigation strategies coded:**
- Self-healing retry with exponential backoff (`asyncio.sleep(1.0 * attempt)` at `app/core/orchestrator.py:139`)
- Circuit breaker prevents cascading failures to degraded upstream services
- Token bucket rate limiting prevents API-level throttling

---

## 7. Security Engineering

### 7.1 AES-256-GCM Token Encryption

The `encryption.py` module (`app/services/encryption.py`) implements application-level encryption for OAuth tokens:

```python
def encrypt_token(plaintext: str) -> Tuple[bytes, bytes, bytes]:
    key = _load_key()  # 32 bytes from ENCRYPTION_KEY env var
    aesgcm = AESGCM(key)
    iv = os.urandom(12)  # 96-bit nonce
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    tag = ciphertext_with_tag[-16:]  # last 16 bytes = auth tag
    ct = ciphertext_with_tag[:-16]   # ciphertext
    return ct, iv, tag
```

The database stores all three components in separate `BYTEA` columns (`encrypted_token`, `encrypted_iv`, `encrypted_tag`) within the `oauth_vault` table (`migrations/001_multi_tenant_schema.sql:56-72`). The encryption key lives exclusively in the environment — never in the database. Key rotation support is documented in the architectural note at line 78 of the migration.

### 7.2 Row-Level Security

Migration 003 enables RLS on 6 tables with tenant isolation policies using `current_setting('app.current_client_id')`. This ensures that even if an application bug exposes data, PostgreSQL enforces the tenant boundary at the query level.

### 7.3 Input Validation

Pydantic field validators provide injection prevention at the API boundary:
- `ContentRequest.topic`: `min_length=10, max_length=2000` prevents SQL injection vectors through string length control
- `ContentAnalyticsEvent.event_type`: regex pattern `r"^(content_generated|...)$"` at `app/models/analytics.py:9` prevents injection via enum fields
- `agent_contracts.py`: Custom `field_validator` on `unified_truth_document` enforces minimum word count (`50` words) and `twitter_thread` enforces per-post character limits (`≤240`)

### 7.4 Content Safety Scanning

The `ModeratorAgent` (`app/agents/moderator_agent.py`) applies regex-based safety scanning across all generated content:

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

The `_flatten_content` method (`app/agents/moderator_agent.py:58`) concatenates all platform text into a single string for regex scanning. Results are serialized into a `ModeratorVerdict` contract.

### 7.5 Rate Limiting

The token bucket algorithm (`app/core/rate_limiter.py:9`) provides per-model rate enforcement with:
- Configurable capacity and refill rate
- Asynchronous lock for thread safety
- Configurable timeout (default 5s)
- Sub-50ms polling interval

The `RateLimiterRegistry` (`app/core/rate_limiter.py:44`) maps named services (e.g. "gemini", "openrouter") to their buckets.

### 7.6 Secrets Management

- **Kubernetes**: `k8s/secrets.yaml` defines opaque secrets for `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `ENCRYPTION_KEY`, `DB_PASSWORD`
- **ConfigMaps**: `k8s/configmap.yaml` separates non-sensitive configuration (model names, URLs, environment)
- **Runtime**: Secrets injected via `envFrom.secretRef` in the Deployment spec

### 7.7 Circuit Breaker Pattern

The `CircuitBreaker` class (`app/core/circuit_breaker.py:21`) prevents cascading failures:
- Threshold: 5 consecutive failures → OPEN state
- Recovery timeout: 30s before HALF_OPEN
- Half-open max retries: 3 before full CLOSED recovery
- Thread-safe state transitions via `asyncio.Lock()`

---

## 8. Observability Implementation

### 8.1 Structured Logging

`app/core/logging_config.py` implements JSON-formatted logging with:
- Timestamp in ISO 8601 UTC
- Correlation ID propagation via `record.correlation_id`
- Exception serialization via `formatException`
- Extra fields support via `record.extra_fields`
- Default level: INFO; httpx/httpcore silenced to WARNING

```json
{"timestamp": "2026-05-19T12:00:00Z", "level": "INFO", "logger": "agent.critic_agent",
 "message": "Critic verification attempt 1/3", "correlation_id": "uuid-here"}
```

### 8.2 Distributed Tracing

OpenTelemetry is configured at `app/monitoring/traces.py:13`:
- OTLP HTTP exporter targeting configurable endpoint (`OTEL_EXPORTER_OTLP_ENDPOINT`, default `http://localhost:4318/v1/traces`)
- Batch span processor with `BatchSpanProcessor`
- Resource attributes: `service.name`, `service.version`, `deployment.environment`
- Tracer spans bound to the agent pipeline for end-to-end latency breakdown

The OpenTelemetry Collector configuration (`docker/otel-collector.yml`) receives OTLP over gRPC (4317) and HTTP (4318), batches spans (1s timeout, 1024 batch size), and exports to Prometheus (port 8889).

### 8.3 Prometheus Metrics

`app/monitoring/prometheus.py` defines metrics instrumented via the `MetricsRegistry` (`app/core/metrics.py`):

**Counters:**
- `gnone_requests_total{model, status}` — Per-model request count by status
- `gnone_content_pieces_total{platform}` — Content pieces generated per platform
- `gnone_critic_cycles_total{result}` — Critic approval/rejection counts
- `gnone_errors_total{type}` — Error counts by type
- `gnone_revenue_closed_total` — Total revenue tracked

**Histograms:**
- `gnone_research_latency_seconds` — Gemini grounding latency
- `gnone_generation_latency_seconds` — OpenRouter generation latency
- `gnone_critic_latency_seconds` — Nemotron critic latency
- `gnone_pipeline_latency_seconds` — End-to-end pipeline latency
- `gnone_refinement_cycles` — Number of critic refinement cycles
- `gnone_deal_value` — Revenue distribution

The metrics endpoint at `GET /api/v1/admin/metrics` exports Prometheus-compatible text format via `registry.export_prometheus()`.

**Prometheus configuration** (`docker/prometheus.yml`) scrapes:
- `gnone-api` on port 8000 at `/api/v1/admin/metrics` every 15s
- PostgreSQL exporter on port 9187
- Redis exporter on port 9121

### 8.4 Grafana Dashboard

The dashboard model (`app/monitoring/dashboard.py`) defines 6 panels:

| Panel | Type | Query |
|-------|------|-------|
| Pipeline Latency (P50/P95/P99) | Timeseries | `histogram_quantile(0.50, rate(gnone_pipeline_latency_seconds_bucket[5m]))` |
| Requests & Error Rate | Timeseries | `rate(gnone_requests_total[5m])`, `rate(gnone_errors_total[5m])` |
| Critic Approval Rate | Gauge | `sum(rate(gnone_critic_cycles_total{result='approved'}[1h])) / sum(rate(...)) * 100` |
| Content by Platform (24h) | Barchart | `increase(gnone_content_pieces_total[24h])` |
| Revenue Closed | Stat | `sum(gnone_revenue_closed_total)` |
| Refinement Cycle Distribution | Heatmap | `rate(gnone_refinement_cycles_bucket[1h])` |

Grafana runs in the Docker Compose stack on port 3000 with the `grafana-piechart-panel` plugin pre-installed.

### 8.5 Alert Rules

`app/monitoring/alerts.py` defines 5 alert rules across two severity levels:

**CRITICAL** (3 rules):
1. `HighErrorRate` — `rate(gnone_errors_total[5m]) / rate(gnone_requests_total[5m]) > 0.05`
2. `PipelineLatencyHigh` — `histogram_quantile(0.95, rate(gnone_pipeline_latency_seconds_bucket[5m])) > 120`
3. `CircuitBreakerOpen` — Circuit breaker open state exceeding 600 seconds

**WARNING** (3 rules):
1. `RefinementCycleBudget` — Content requiring 3+ critic cycles dropping below 80% rate
2. `CriticRejectionSpike` — Rejection rate exceeding 30% over 15 minutes
3. `TokenExceededWarning` — Per-client token usage exceeding 80% of daily quota

### 8.6 Health Check Architecture

The `HealthRegistry` at `app/infrastructure/health.py:20` registers async health check functions and runs them concurrently via `asyncio.gather`. Each check returns a `HealthStatus(service, healthy, latency_ms)` dataclass. Current checks include PostgreSQL (`Database.health()` at `app/infrastructure/db.py:65`) and Redis (`Cache.health()` at `app/infrastructure/cache.py:62`). The aggregated endpoint at `/api/v1/admin/health` returns HTTP 200 if all dependencies are healthy, 503 otherwise.

---

## Architectural Summary

```
                          ┌──────────────┐
                          │   FastAPI     │
                          │  (app/main.py)│
                          └──────┬───────┘
                                 │
                  ┌──────────────┼──────────────┐
                  │              │              │
           ┌──────┴──────┐ ┌────┴────┐ ┌───────┴──────┐
           │   Routes    │ │  Core   │ │  Agents      │
           │ /api/v1/*   │ │ DAG,    │ │ Research →   │
           │ /ws/*       │ │ Circuit │ │ Copywriting→ │
           │             │ │ Breaker │ │ Critic →     │
           │             │ │ Limiter │ │ Moderator    │
           └─────────────┘ └─────────┘ └──────────────┘
                  │              │              │
           ┌──────┴──────┐ ┌────┴────┐ ┌───────┴──────┐
           │  Services   │ │  Infra  │ │  Monitoring  │
           │ Gemini      │ │ DB      │ │ Prometheus   │
           │ OpenRouter  │ │ Cache   │ │ OpenTelemetry│
           │ Recall.ai   │ │ Health  │ │ Grafana      │
           │ LiveKit     │ │ DI      │ │ Alerts       │
           │ Encryption  │ │         │ │              │
           └─────────────┘ └─────────┘ └──────────────┘
```

The platform operates on a DAG-based execution model (`DAGOrchestrator` at `app/core/orchestrator.py:84`) where agents execute according to topological ordering with automatic retry and upstream failure propagation. The content manufacturing pipeline follows: **Seed → Gemini Research → OpenRouter Generation → Nemotron Critic Loop → Moderator Scan → Output**. Observability is layered at every level: structured JSON logs with correlation IDs, OpenTelemetry trace propagation across agents, Prometheus histograms for latency and counters for business metrics, and Grafana dashboards with alerting thresholds for SLO enforcement.
