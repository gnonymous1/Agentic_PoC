# Architecture Agent Evaluation: GNONE Sovereign Executive Proxy Engine

**Evaluator:** Principal Cloud Architect (Architecture Agent)
**Date:** 2026-05-19
**Classification:** Internal — Strictly Confidential

---

## 1. Executive Verdict

**Score: 5.5 / 10 — "Promising prototype with critical production gaps that will cause cascading failures under real load."**

The architecture documentation paints a picture of a distributed, resilient microservice fabric. The actual codebase reveals a single-process monolithic FastAPI application with asynchronous orchestration. This disconnect between documented architecture and implementation is the single biggest risk. The platform's core ideas (DAG orchestration, critic loop, RLS multi-tenancy) are sound, but the production-readiness posture has fundamental gaps in scalability, fault isolation, security operations, and deployment discipline.

---

## 2. Topology & Decomposition

### Microservice Boundaries: Documented vs. Actual

The `ARCHITECTURE.md` describes a "distributed, decoupled microservice cluster" with separate agent execution nodes, an API gateway, a LiveKit matrix, and a Recall.ai container manager. The actual deployment tells a different story:

- **Single binary, single deployment.** All agents (Research, Copywriting, Critic, Moderator) execute **in-process** via `DAGOrchestrator.run()` (`app/core/orchestrator.py:105`). There is no separate service for agent execution. The entire system is a single FastAPI deployment (`k8s/deployment.yaml`) with one container image.
- **No service mesh.** Nothing resembling Istio, Linkerd, or Consul Connect exists. There are no `ServiceEntry` or `DestinationRule` resources. The ingress (`k8s/ingress.yaml`) routes directly to the `gnone-api` ClusterIP service with no intermediate mesh layer.
- **No NetworkPolicy.** The architecture report's 4-tier network segmentation (`reports/architecture_report.md:71-108`) is aspirational. The Kubernetes manifests contain zero `NetworkPolicy` resources. Any pod in the cluster can talk to any other pod. The "Tier 2 Agent Execution" / "Tier 3 Data Layer" isolation exists only in the slide deck.
- **Two conflicting service types.** The Service manifest (`k8s/service.yaml`) exposes both a ClusterIP (port 80 → 8000) and a LoadBalancer (port 443 → 8000). The LoadBalancer on port 443 terminates TLS at the cloud LB level, but the Ingress also terminates TLS — double termination creates confusion. Worse, the LoadBalancer type exposes every pod directly to the internet, bypassing the Ingress rate limiting and WAF capabilities.

### What's Missing

- **A dedicated ingestion service.** Webhooks, calendar events, and RSS feeds all land on the same FastAPI process. If a webhook storm occurs (e.g., 1000 calendar sync events in one minute), the manufacturing pipeline competes for the same process pool. Webhook ingestion should be a separate deployment with its own HPA.
- **A DLQ reconciler service.** Discussed in Section 4.
- **A session manager for LiveKit.** The voice agent connects to LiveKit tracks via WebSockets, but there is no dedicated session management service to handle room lifecycle, participant limits, or reconnection state.
- **A job scheduler.** The Redis task queue (`app/services/redis_queue.py`) provides at-least-once delivery but has no cron/scheduling capability. There is no mechanism for "publish this content at 9:00 AM" or "retry this failed job in 2 hours."

### API Gateway Considerations

The ingress uses `nginx.ingress.kubernetes.io/rate-limit-rps: 100` (`k8s/ingress.yaml:9`), which is a Node-level rate limit — not a true per-client rate limit. Nginx ingress rate limiting is based on the `ngx_http_limit_req_module` and uses remote IP. Behind a load balancer, all traffic appears to come from the LB's internal IP, making this rate limit effectively a global one. Consider using `nginx.ingress.kubernetes.io/limit-rps` with the `limit-key` annotation set to `$http_x_forwarded_for` or, better, implement token-based rate limiting at the application layer keyed on the JWT client ID.

---

## 3. Scalability Analysis

### HPA: CPU-Bound vs. IO-Bound Mismatch

The HPA (`k8s/hpa.yaml`, `k8s/deployment.yaml:61-85`) uses CPU and memory utilization as scaling signals:

```yaml
metrics:
  - resource: { name: cpu,  target: { type: Utilization, averageUtilization: 70 } }
  - resource: { name: memory, target: { type: Utilization, averageUtilization: 80 } }
```

This workload is **IO-bound, not CPU-bound.** Each content manufacturing cycle spends 90%+ of its time waiting on external API calls: Gemini grounding (2-8s), OpenRouter generation (3-10s), Nemotron critic (2-5s). During these waits, the Python process is blocked in `asyncio` but the CPU utilization is near zero. A CPU-based HPA will **never trigger scale-up** because CPU stays low even when the system is saturated with concurrent requests.

The correct scaling metric is **request concurrency** or **queue depth**. Use a custom metrics adapter (Prometheus Adapter) to scale on:
- `sum(rate(httpx_active_requests[1m]))` — concurrent outbound HTTP requests
- `gnone_queue_depth` — Redis queue length for the manufacturing queue

With `--workers 4` (`Dockerfile:28`) and `max_connections=25` per pool, each pod can handle ~20 concurrent manufacturing requests. At 70% CPU (which will never be reached), the pod is barely loaded. The HPA should be reconfigured for `type: Pods` with a custom metric.

**Capacity planning error.** The report claims "~400-800 requests per minute" at 20 replicas (`reports/architecture_report.md:269`). With each request taking 10-20 seconds of wall-clock time for external API calls, and each pod handling ~4 concurrent requests (with 4 workers × 25 pool connections), the actual throughput at 20 replicas is closer to **20 × (4 concurrency / 15s avg latency) = ~5.3 RPM**. This is **100x lower** than the documented estimate. The throughput estimation confuses latency with throughput and ignores the sequential nature of the DAG.

### Database Connection Pooling: A Looming Disaster

The `Database` class (`app/infrastructure/db.py:31-38`) configures `min_size=5, max_size=25` per pool:

```python
pool = await asyncpg.create_pool(dsn=config.dsn, min_size=5, max_size=25, ...)
```

This is one pool per process. The Dockerfile runs **4 Uvicorn workers** (`Dockerfile:28`): `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]`.

This means **4 processes × 25 connections = 100 connections per pod**. At 20 replica pods, that is **2000 database connections**.

The report acknowledges that PostgreSQL `max_connections` must be overridden from 100 to 600 (`reports/architecture_report.md:284`). But 600 is still 3x too low for 2000 connections. Even 600 connections consumes significant PostgreSQL memory (each connection uses ~10MB for work_mem, sort buffers, etc.), requiring 6GB+ just for connection overhead on a database that should have <50 active connections.

**Root cause:** asyncpg pools are process-scoped. With `--workers 4`, you get 4 independent pools. The solution is either:
1. Remove `--workers 4` and use Uvicorn's single-process mode with `--workers 1`. Scale horizontally via HPA instead of vertically via worker processes. Single-process asyncpg pool of 25 connections × 20 pods = 500 connections — still high but manageable with PostgreSQL at `max_connections=600`.
2. Or use a centralized PgBouncer/PgCat connection pooler in transaction mode. This allows 1000+ application connections to multiplex over 50-100 actual PostgreSQL connections.

### Redis: Single Point of Failure

The docker-compose (`docker/docker-compose.yml:50-58`) runs a vanilla `redis:7-alpine` with no persistence configuration, no replication, no Sentinel. In Kubernetes, there's no Redis StatefulSet manifest at all — it's presumably run externally.

The task queue uses `BRPOP` (`app/infrastructure/cache.py:57`) with blocking semantics. If Redis restarts (e.g., OOM, pod eviction, maintenance):
1. All in-flight jobs are lost (no AOF/RDB configured).
2. All deduplication keys are lost, allowing duplicate processing.
3. All rate limiter state is lost, potentially causing a burst of 429s or, worse, allowing over-quota usage.
4. All pods block on `BRPOP` indefinitely, requiring application restart to reconnect.

**Required:**
- Redis Sentinel or Redis Cluster for high availability.
- AOF persistence with `appendfsync everysec`.
- `retry_on_timeout=True` is already set (`cache.py:16`) but there's no reconnection logic if the connection drops entirely.
- Rate limiter state should be persisted more durably, or switch to local in-memory token buckets with periodic Redis sync.

### pgvector HNSW: Index Parameters

The HNSW index (`migrations/001_multi_tenant_schema.sql:213-216`) uses:

```sql
WITH (m = 16, ef_construction = 200)
```

`m=16` is the standard default for 1536-dimensional embeddings. `ef_construction=200` provides high recall (≥0.97) at the cost of ~2x longer index build time and ~3x more memory during construction. These values are **reasonable for offline batch indexing** but suboptimal for real-time ingestion:

- **ef_construction=200** vs the default (typically 100-128): This doubles index build time. If embeddings are ingested in real-time during live calls, each insertion blocks the HNSW graph update for 5-15ms. Under concurrent inserts, this causes index bloat and degraded query performance. Use `ef_construction=128` for real-time workloads and accept the 0.01 recall hit.

- **No tenant-aware filtering in the index.** The HNSW index is built over ALL tenant embeddings. The query will include `WHERE client_id = ?`, but PostgreSQL HNSW does not support index-accelerated filtering on non-indexed columns. At >10M embeddings across all tenants, the ANN search scans vectors from unrelated tenants, increasing latency. Consider creating **per-tenant partial indexes** or adding `client_id` as an HNSW indexed dimension (not possible with pgvector's current operator classes). Alternative: use a separate `ivfflat` index per tenant, or implement tenant-specific vector tables if the tenant count is manageable (<100).

- **`vector_cosine_ops` is correct** for cosine similarity on normalized embeddings. No issue here.

---

## 4. Fault Tolerance Review

### Circuit Breaker: Half-Open Retries and Recovery Timeout

```python
# app/core/circuit_breaker.py:14-18
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_retries: int = 3
```

**`recovery_timeout=30s`:** This is aggressive but workable for transient failures (e.g., network hiccup, DNS resolution blip). However, model API outages (OpenRouter, Gemini) typically last 2-15 minutes during degradation events. A 30-second recovery timeout means the circuit enters HALF_OPEN during the outage window, the 3 probes fail, it re-enters OPEN, and 30 seconds later it probes again. This creates **rapid cycle thrashing**: every 30 seconds, the system sends 3 probe requests that will fail, wasting API quota and adding latency to the first request that hits each cycle. A more appropriate value is `recovery_timeout=120s` for model APIs, with exponential backoff on subsequent cycles.

**`half_open_max_retries=3`:** Three probe requests in HALF_OPEN is one too many. In probe mode, you want to validate recovery with **one** successful request, then immediately close. Three probes triple the latency for the unlucky request that triggers the transition. Change to `half_open_max_retries=1`.

**`failure_threshold=5`:** This is reasonable. With 5 consecutive failures before opening, the circuit tolerates isolated errors.

### Critical Bug: Race Condition in HALF_OPEN Transitions

In `circuit_breaker.py:49-54`:

```python
if self._state == CircuitState.HALF_OPEN:
    if self._half_open_attempts >= self.config.half_open_max_retries:
        self._state = CircuitState.CLOSED    # BUG: transitions to CLOSED without a successful probe
```

This code transitions from HALF_OPEN to CLOSED when `half_open_attempts >= max_retries`, regardless of whether any probe succeeded. Combined with the reset-on-success at lines 66-69, the state machine can transition to CLOSED after 3 failed probes because `half_open_attempts` increments on every HALF_OPEN entry. The correct logic should only transition to CLOSED after `half_open_max_retries` **successful** probes, not after `half_open_max_retries` entries.

### Error Budget: Defined but Never Enforced

The `ErrorBudget` dataclass (`app/core/errors.py:53-74`) tracks `total_operations` and `failed_operations` per service, but:

1. **No one calls `record_success()`.** The `record_success()` method exists (line 61) but is never invoked anywhere in the codebase. Only `record_failure()` is wired in.
2. **No Prometheus metrics emit from ErrorBudget.** Without metrics, `is_exhausted` cannot drive alerting or automated degradation.
3. **No throttling logic consumes it.** The `is_exhausted` property returns `True` when `error_budget_remaining <= 0.0`, but no code checks this before calling an API. The circuit breaker handles the failure side, but the error budget should proactively prevent calls when the budget is exhausted.
4. **The 30-day sliding window is aspirational.** The current implementation is a running counter that never resets — `error_budget_remaining` only goes down until the process restarts. There's no time-windowed calculation.

### The "All 3 Critic Retries Fail" Scenario

When the critic loop exhausts all retries, `critic_verification_loop()` raises `MaxRetriesExceededError` (`app/services/critic_loop.py:150`). The `CriticAgent.execute()` catches this gracefully (`app/agents/critic_agent.py:31-37`), marks `critic_approved=False`, and returns best-effort content.

However, there's a critical gap in the critic loop itself. If `call_critic()` fails with a **network error** (timeout, connection reset, 5xx) rather than a critic rejection, the code still decrements the retry budget. Three consecutive network errors mean the content is returned unverified — not just best-effort but **unreviewed**. The flow should distinguish between:
- **Rejection failures** (critic reviewed but rejected): return best-effort with refinement notes.
- **System failures** (network error, API down): retry transparently with exponential backoff, independent of the critic rejection retry budget.

The current code conflates both failure modes into a single retry counter (`settings.max_retries`).

### Dead Letter Queue: Orphaned Data

The `TaskQueue.process()` (`app/services/redis_queue.py:65-73`) routes failed jobs to `{queue}:deadletter`:

```python
except Exception:
    await cache.enqueue(f"{queue}:deadletter", job_data)
    raise   # <-- This terminates the consumer
```

The `raise` on line 73 immediately kills the processing loop. The DLQ entry is written but never consumed because:

1. **There is no DLQ consumer/reconciler.** The report mentions "an independent worker ('the DLQ reconciler')" (`reports/architecture_report.md:460`), but no such worker exists in the codebase. No Python file, no Kubernetes job, no cron entry.
2. **The process crashes on the first DLQ write.** The `while True` loop in `process()` runs forever, but `raise` on the first exception exits the coroutine entirely. The pod-level supervisor (Kubernetes/Docker) restarts the container, but now the DLQ entry from the previous run is orphaned.
3. **DLQ entries have no TTL.** The `enqueue` call for DLQ doesn't set an expiry, so dead jobs accumulate in Redis forever.

**This is not just a gap — it's a data loss risk.** A transient error in the handler causes the job to be lost forever (unless the operator manually inspects the Redis keyspace). The DLQ needs a dedicated consumer that re-queues jobs with exponential backoff, up to N retries, then archives to PostgreSQL for forensic analysis.

---

## 5. Infrastructure Gaps (CRITICAL)

### SSL/TLS: Ingress Only

The ingress terminates TLS using cert-manager (`k8s/ingress.yaml:11-14`). Internal traffic between the API pod and PostgreSQL, Redis, and LiveKit travels in plaintext:

- **FastAPI to PostgreSQL:** Password is sent in cleartext (`postgresql://gnone:gnone@postgres:5432/gnone` in `docker-compose.yml:13`). In production, there is no SSL/TLS between the app and the database. An attacker with network access to the pod network (no NetworkPolicy) can sniff all queries and data.
- **FastAPI to Redis:** No TLS. Redis passwords (if any) are sent in cleartext.
- **No mTLS.** There is no mutual TLS between any services. In zero-trust architectures (which this should be given the sensitive nature of OAuth tokens in the vault), every service-to-service call should be mTLS-authenticated. Consider a service mesh (Istio/Linkerd) or a sidecar proxy.

### Secret Rotation: The Encryption Key Is Not Rotatable

The `encrypt_token()` function (`app/services/encryption.py:22-35`) loads the encryption key from the `ENCRYPTION_KEY` environment variable on every call:

```python
def _load_key() -> bytes:
    key_hex = os.getenv("ENCRYPTION_KEY")
    return bytes.fromhex(key_hex)
```

The `oauth_vault` schema (`migrations/001_multi_tenant_schema.sql`) mentions `key_version` in a SQL comment (lines 110-114), but **the actual table has no `key_version` column.** The schema comment is wishful thinking, not an implemented feature.

To rotate the key:
1. Change `ENCRYPTION_KEY` in the environment.
2. Every `encrypt_token()` call now uses the new key.
3. Every `decrypt_token()` call that uses the old key will **fail with an authentication error** because the GCM tag won't verify.

**This means key rotation is an unsupported operation.** All existing encrypted data becomes permanently undecryptable after a key change. The only workaround is:
- Schedule downtime.
- Read every row in `oauth_vault`, decrypt with old key, re-encrypt with new key, write back.
- Deploy with the new key.

This is a **production-blocking** issue. The fix requires either:
1. A `key_version` column and a versioned key ring (storing old keys in the application or vault).
2. Use envelope encryption (KMS key encrypts a data key, data key encrypts tokens) so only the data key needs rotation.
3. Or use a dedicated secrets management system (HashiCorp Vault transit engine, AWS KMS) for on-the-fly rewrap.

### Backup Strategy: None Documented

There is no backup strategy anywhere in the codebase or documentation. Specific gaps:

- **PostgreSQL:** No WAL archiving configuration, no `pg_basebackup` cron, no Point-in-Time Recovery (PITR) capability. The analytics event table has monthly partitions and an auto-drop function for partitions older than 90 days (`migrations/003_audit_logging.sql:48-64`), but this is a retention policy, not a backup strategy. Without WAL archiving, the recovery point objective (RPO) is the last manual `pg_dump`.
- **Redis:** No RDB or AOF persistence configuration. The `redis:7-alpine` image has persistence disabled by default. The docker-compose mounts a volume (`docker-compose.yml:57`) but Redis won't write RDB snapshots without explicit `save` directives. On restart, the entire task queue, deduplication keys, and rate limiter state are lost.
- **pgvector embeddings:** Rebuilding the HNSW index after data loss requires re-embedding all source documents, which is computationally expensive and requires all source data to be available.

### No CDN

Blogspot HTML content is served directly from the application. Given that Blogspot content includes static HTML pages with SEO-sensitive markup, the absence of a CDN means:
- Higher latency for geographically distant readers.
- No edge caching for repeated requests.
- No DDoS protection at the edge (Cloudflare, AWS CloudFront, Fastly).

For a platform that generates and hosts content, this is a significant missed optimization. Blogspot HTML should be pushed to a CDN (or at minimum to a Blob storage + CDN) on approval.

### Rate Limiting: Per-Client Gap

The application layer rate limiter (`app/core/rate_limiter.py`) is organized **per model**, not per client:

```python
rate_limiter.register("gemini-3.1-flash-lite",  capacity=60,  refill_rate=1.0)
rate_limiter.register("openai/gpt-oss-120b:free", capacity=30,  refill_rate=0.5)
rate_limiter.register("nvidia/nemotron-3-super",  capacity=20,  refill_rate=0.33)
```

With `clients` having `daily_content_quota` (`migrations/001_multi_tenant_schema.sql:42`), there is no enforcement of per-client quotas. A single rogue client could submit 1000 manufacturing requests per minute, exhausting the free model API quota for all other clients. The daily_content_quota column exists in the schema but is never checked at runtime.

The ingress rate limit (100 RPS) is the only per-client (by IP) protection, and it's trivially bypassed with a multi-region botnet.

---

## 6. Deployment Readiness

### Docker Healthcheck: Python Overhead

The Dockerfile (`Dockerfile:22-23`) defines:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health')"
```

This spawns a **full Python interpreter** (with `httpx` import overhead) every 30 seconds. Each health check takes 200-400ms just in Python startup time, plus the HTTP request. With `import httpx`, this imports the entire httpx library (including certifi, httpcore, etc.) from scratch.

Compare with `curl`:
```dockerfile
HEALTHCHECK CMD curl -f http://localhost:8000/api/v1/health || exit 1
```
curl is an ~100KB binary that starts in <5ms. The Python version adds 50-100ms of latency per check for zero benefit. The Dockerfile already installs `curl` (`Dockerfile:11`) — use it.

### Kubernetes: Missing Critical Resources

The deployment manifest (`k8s/deployment.yaml`) is minimal. Missing:

1. **No PodDisruptionBudget (PDB).** Without a PDB, during voluntary node disruptions (e.g., cluster autoscaler scale-down, node pool upgrades), all 3 API pods can be evicted simultaneously, causing a full outage. A PDB with `minAvailable: 2` is essential.

2. **No PriorityClass.** The API deployment has no `priorityClassName`. In a cluster with mixed workloads, a lower-priority batch job could preempt the only remaining API pod. The API deployment should use a high-priority PriorityClass (e.g., `platform-critical`) with a preemption policy of `PreemptLowerPriority`.

3. **No `terminationGracePeriodSeconds`.** The default is 30 seconds. The API pod handles in-flight WebSocket connections and async tasks. On shutdown, the pod is SIGTERMed after 30 seconds, which may not be enough to drain active manufacturing pipelines. Set to `terminationGracePeriodSeconds: 120` and implement proper `app.on_event("shutdown")` handling.

4. **No `topologySpreadConstraints`.** All 3 replicas could be scheduled on the same node. With `--topologySpreadConstraints: maxSkew: 1, topologyKey: kubernetes.io/hostname`, pods are spread across nodes for high availability.

### Canary Deployments

The CD pipeline (`cd.yml`) runs a single `kubectl set image` command:

```yaml
- name: Deploy to Kubernetes
  run: |
    kubectl set image deployment/gnone-api \
      api=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.ref_name }} \
      -n gnone
```

This is a direct rolling update with no canary, no smoke tests, no metrics verification. If the new image has a bug that causes 500 errors:
1. Kubernetes replaces all 3 pods one by one.
2. The error rate spikes.
3. The rolling update **does not automatically roll back.** Kubernetes only checks the readiness probe — if the probe returns 200, the rollout continues even if business logic is broken.
4. There is no automated rollback trigger.

A proper deployment strategy requires:
- A canary phase: deploy 1 new pod alongside 3 old pods, verify metrics for 5 minutes.
- Smoke tests: run a synthetic manufacturing request against the canary pod and verify the output.
- Progressive traffic shift (e.g., 10% → 50% → 100%) using a service mesh or Flagger/Argo Rollouts.
- Automated rollback if error rate exceeds 1% or P95 latency exceeds threshold.

### Database Migrations in Kubernetes

The docker-compose runs migrations by mounting the `migrations/` directory to `/docker-entrypoint-initdb.d` (`docker-compose.yml:42`), which only runs on initial database setup. Subsequent migrations are never applied.

In Kubernetes, there is:
- No init container for migrations.
- No Kubernetes Job for migration execution.
- No Alembic or migration versioning tool.

This means:
- Migration `003_audit_logging.sql` (which enables RLS and creates partitions) is never applied in production.
- Any schema change requires manual `kubectl exec` into a pod and running SQL — error-prone and not repeatable.

**Required:** A dedicated `kubemigrate` or plain migration Job in the CD pipeline, executed before the deployment rollout:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: gnone-migrate-003
  namespace: gnone
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: postgres:16
          command: ["psql", "$DATABASE_URL", "-f", "/migrations/003_audit_logging.sql"]
```

---

## 7. Recommendations (Top 5 Actionable)

### 1. Fix the Process Architecture and Connection Scaling **(Critical — Safety)**

**Problem:** 4 Uvicorn workers × 25 asyncpg connections × 20 pods = 2000 database connections. PostgreSQL cannot handle this. The CPU-based HPA never scales because the workload is IO-bound.

**Action:**
- Remove `--workers 4` from the Dockerfile CMD. Use single-process Uvicorn (`--workers 1`). Scale horizontally via HPA instead.
- Change HPA metrics from CPU/memory to **request concurrency** using a custom Prometheus metric (e.g., `gnone_in_flight_requests` from httpx instrumentation) or Redis queue depth.
- Reduce asyncpg pool to `max_size=10` (single-process × 10 connections × 20 pods = 200 — manageable).
- Implement connection throttling: if the pool is exhausted, queue the request rather than letting it block indefinitely.

### 2. Implement Key Rotation for the Encryption Vault **(Critical — Security)**

**Problem:** The `ENCRYPTION_KEY` cannot be rotated without decrypting all data with the old key first. The `oauth_vault` table has no `key_version` column despite the schema comment claiming otherwise.

**Action:**
- Add a `key_version` column (INTEGER NOT NULL DEFAULT 1) to `oauth_vault`.
- Implement a versioned key ring: store `ENCRYPTION_KEY_V1`, `ENCRYPTION_KEY_V2` etc. in environment variables or a secrets manager.
- Modify `_load_key()` to accept a `key_version` parameter and read the corresponding key.
- Add a rotation endpoint (`POST /api/v1/admin/rotate-encryption-key`) that iterates all rows, decrypts with old key, re-encrypts with new key, increments `key_version`.
- Until this is implemented, establish a manual rotation runbook with documented downtime.

### 3. Add a DLQ Reconciler and Fix Redis Durability **(Critical — Data Integrity)**

**Problem:** The DLQ receives entries but no consumer processes them. The `raise` on exception kills the consumer loop. Redis has no persistence configuration.

**Action:**
- Fix `TaskQueue.process()` to catch exceptions, enqueue to DLQ, and **continue** the loop rather than raising:

```python
async def process(self, queue: str, handler):
    while True:
        job_data = await self.dequeue(queue)
        if job_data:
            try:
                await handler(job_data["payload"])
            except Exception as e:
                await cache.enqueue(f"{queue}:deadletter", job_data)
                logger.error("Job %s failed: %s", job_data["id"], e)
```

- Implement a `DLQReconciler` that re-queues dead jobs with exponential backoff (1m, 5m, 30m, 2h, 6h, 24h) up to 5 retries, then archives to `audit_log`.
- Enable Redis AOF persistence (`appendonly yes`, `appendfsync everysec`).
- Add Redis Sentinel or use ElastiCache/Memorystore in production.

### 4. Add Per-Client Rate Limiting and Quota Enforcement **(High — Operations)**

**Problem:** Rate limits are per-model, not per-client. The `daily_content_quota` column in `clients` table is never checked.

**Action:**
- Add a wrapper in the manufacturing route that checks `daily_content_quota` against today's usage (from `api_usage_quotas` table).
- Implement a two-tier rate limiter: a global per-model token bucket (existing) AND a per-client token bucket keyed on `client_id`.
- Add per-client rate limit headers to API responses (`X-RateLimit-Remaining`, `X-RateLimit-Reset`).
- Reconfigure the ingress rate limit to use `$http_x_forwarded_for` or the JWT claim as the limiting key via an nginx auth_request to the application.

### 5. Fix Kubernetes Production Readiness **(High — Reliability)**

**Problem:** No PDB, no PriorityClass, no NetworkPolicy, no migration Job, no canary deployment.

**Action:**
- Add `PodDisruptionBudget` with `minAvailable: 2`.
- Add `priorityClassName: gnone-critical` (create the PriorityClass with `value: 1000000`).
- Add `NetworkPolicy` resources enforcing the 4-tier segmentation described in the architecture report.
- Add a migration Job to the CD pipeline, executing before the deployment update.
- Replace `kubectl set image` with Argo Rollouts or Flagger for canary deployments with automated metric verification and rollback.
- Change healthcheck from `python -c "import httpx..."` to `curl -f http://localhost:8000/api/v1/health`.

---

## Summary of Scoring

| Category | Score | Assessment |
|---|---|---|
| Topology & Decomposition | 4/10 | Monolith disguised as microservices. No NetworkPolicy. No service mesh. |
| Scalability | 3/10 | Wrong HPA metric. 2000 DB connections. Redis SPOF. pgvector indexes not tenant-filtered. |
| Fault Tolerance | 5/10 | Circuit breaker has state machine bug. DLQ has no consumer. Error budget not wired. Critic loop conflates network errors with rejections. |
| Infrastructure | 4/10 | No mTLS. Key rotation impossible. No backups. No CDN. No per-client rate limiting. |
| Deployment Readiness | 3/10 | Python healthcheck. No PDB/PriorityClass. No migration strategy. No canary. |
| Architecture Documentation | 8/10 | Good documentation but significantly diverges from implementation. |
| **Overall** | **5.5/10** | |

The platform has a well-considered foundation (DAG orchestration, RLS multi-tenancy, pgvector, AES-256-GCM encryption) but is 3-6 months of disciplined engineering work away from production readiness at scale. The top three risks — connection pool explosion, non-rotatable encryption keys, and orphaned DLQ entries — should be addressed before putting real customer data through the system.
