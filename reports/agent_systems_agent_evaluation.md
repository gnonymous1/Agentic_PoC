# GNONE Multi-Agent Systems Evaluation

**Evaluator:** Agent Systems Agent (World-Class Multi-Agent Architecture Expert)
**Date:** May 19, 2026
**Target:** GNONE Sovereign Executive Proxy Engine — Agent Systems Architecture

---

## 1. Executive Verdict

**Score: 4.5 / 10**

The GNONE agent architecture has sound individual abstractions (Pydantic contracts, service-layer isolation, OpenTelemetry instrumentation) but the orchestration layer is a **documented fiction** — the DAGOrchestrator and all five agent classes are dead code bypassed by the actual API route, agent-to-agent communication uses shared mutable state which is a fundamental multi-agent anti-pattern, and there is zero use of industry-standard agent frameworks or protocols. The system as implemented is a **sequential procedural pipeline** dressed in DAG clothing.

---

## 2. Orchestration Architecture Assessment

### 2.1 Custom DAG vs. Framework-Based Orchestration

The `DAGOrchestrator` (`app/core/orchestrator.py:84`) uses Python's `graphlib.TopologicalSorter` to produce a flat execution plan. This is a **correct but minimal** approach. The tradeoffs:

| Dimension | Custom (graphlib) | LangGraph | AutoGen | CrewAI |
|-----------|-------------------|-----------|---------|--------|
| State management | Manual `AgentContext` dataclass | Built-in `State` with reducer functions | Built-in `ConversableAgent` with message history | Role-based shared context |
| Conditional edges | Not supported — would need manual `if/else` | Built-in `add_conditional_edges` | Conversation patterns handle this | `@task` decorators with conditions |
| Human-in-the-loop | Not supported | `interrupt_after` / `Command(resume=)` | `UserProxyAgent` | Built-in input handling |
| Parallel execution | Not implemented (`static_order()` is flat) | `fanout` / `fanin` via `Send` | GroupChat with speaker selection | Parallel task execution |
| Persistence / checkpointing | None | `MemorySaver` / `SqliteSaver` / Postgres | Built-in | Built-in |
| Testing / debugging tools | None | LangSmith | AutoGen Studio | CrewAI Enterprise |

**Verdict:** The custom approach buys zero expressive power while losing all framework benefits. The main argument for staying custom would be dependency minimization, but the current implementation doesn't leverage any custom optimization that a framework couldn't provide.

### 2.2 Sequential Execution Masquerading as a DAG

`static_order()` returns a flat ordered list — NOT grouped by topological level. The execution loop at line 109 iterates sequentially:

```python
for agent_name in plan:  # flat iteration, one at a time
```

Even if the graph had parallel branches (e.g., TwitterAgent and LinkedInAgent both depending on ResearchAgent), they would run sequentially. True concurrent execution would require:

```python
ts = TopologicalSorter(graph)
ts.prepare()
while ts.is_active():
    batch = ts.get_ready()           # ← agents at same depth level
    results = await asyncio.gather(   # ← actual parallelism
        *[self._run_agent(name, ctx) for name in batch]
    )
    ts.done(*batch)
```

The current pipeline has **zero independent branches** anyway — every agent depends on the previous one — making the DAG a **monolithic pipeline with extra ceremony**. There is no parallelizable structure, so the DAG abstraction adds complexity without providing any benefit over a simple sequential script.

### 2.3 State Management — Shared Mutable Context

`AgentContext` (`orchestrator.py:22`) is a mutable dataclass passed by reference to every agent. The sequential execution prevents race conditions, but this design has deeper problems:

1. **No immutability guarantees**: Any agent can modify any field at any time. Agent C can read (and overwrite) data produced by Agent A even if C is not a downstream dependency of A. The dependency graph is enforced only at execution ordering, not at the data-access level.

2. **No message isolation**: If an agent crashes after partially writing to the context, the context contains a corrupted mix of old and new data. With a message-passing architecture, the failed agent's uncommitted messages would simply never be delivered.

3. **Implicit coupling**: Every agent implicitly depends on every field of AgentContext. Adding a field requires auditing every agent. Removing a field requires the same. This is the opposite of the dependency-inversion principle.

---

## 3. Agent Contract Design Review

### 3.1 Contracts Are Created Inside Agents, Not Enforced by the Orchestrator

In `research_agent.py:20-23`:

```python
contract = ResearchContract(
    topic=ctx.topic,
    unified_truth_document=utd,
)
ctx.unified_truth_document = contract.unified_truth_document
```

The contract is created *inside* the agent and its validation only fires if the agent chooses to create it. A buggy agent could simply skip contract creation entirely and write raw data directly to the context. The **orchestrator should enforce contract boundaries** — it should call `agent.execute()`, get back a raw result, validate it against the agent's declared output contract, and *then* write it to the context.

**Recommended pattern:**

```python
# In orchestrator:
raw_result = await agent.execute(ctx)
contract = agent.output_contract.model_validate(raw_result)
ctx = write_contract_to_context(contract)
```

### 3.2 CriticVerdict.corrected_payloads Has No Schema Enforcement

`CriticVerdict` at `agent_contracts.py:51`:

```python
corrected_payloads: dict = Field(default_factory=dict)
```

This is an untyped dictionary. The `critic_loop.py:132-136` validates it against `MultiPlatformContent`, but if the critic model returns a dict that doesn't match, the error is caught only at the point of use, not at the contract boundary. A `Union[MultiPlatformContent, dict]` with a discriminated union or at least `dict[str, Any]` with documented expectations would be marginally better, but what's really needed is:

```python
# What should exist:
corrected_payloads: Optional[MultiPlatformContent] = None
```

This would give Pydantic-level validation at the contract instantiation point, not deferred to a `model_validate` call two modules away.

### 3.3 No Contract for Final Output

`ContentResponse` (`schemas.py:24`) is a separate schema from the agent contracts. If a new agent is added at the end of the pipeline (e.g., a deployment scheduling agent), there is no contract enforcement between the last agent and the API response. The `ContentResponse` schema is hardcoded in the route handler (`content_manufacturing.py:98-105`), which means:
- Adding a new output field requires editing both the agent and the route
- There's no way to validate that the final output conforms to a contract before returning it
- The `utd_summary: str` field is populated by `utd[:500]` — a silent truncation with no validation

### 3.4 Dead Contracts

`CopywritingContract` (`agent_contracts.py:30`) and `DeploymentContract` (`agent_contracts.py:66`) and `ModeratorVerdict` (`agent_contracts.py:57`) are defined but **never instantiated anywhere in the running code**. The actual data flow bypasses these models entirely:

- CopywritingAgent writes `MultiPlatformContent.model_dump()` directly to `ctx.generated_content`
- The route never calls the ModeratorAgent
- DeploymentContract is literally unreferenced

This is either dead code or a gap between documented intent and implementation.

---

## 4. Agent Communication Protocol

### 4.1 Shared Mutable Context Violation

The architect's report claims "agents communicate exclusively through the AgentContext dataclass" as a positive design feature. In practice, this is a **shared-nothing architecture violation**. Proper multi-agent systems use message-passing for several reasons:

1. **Auditability**: With message passing, every communication between agents is an explicit, serializable event. With shared context, the history of "who wrote what and when" must be reconstructed from log entries.

2. **Isolation**: In message-passing, Agent A and Agent B communicate through a well-defined channel with a schema they both agree on. In shared context, any agent can read any field — there is no access control.

3. **Crash containment**: If an agent crashes mid-write to a shared context, the context is corrupted. With message queues, the failed agent's unprocessed messages remain in the queue for retry, and the messages it successfully sent are already delivered.

4. **Testing**: Testing a message-passing agent requires mocking only the messages it receives. Testing a context-based agent requires constructing the entire `AgentContext` with all upstream fields populated.

### 4.2 Dependency Isolation Is Broken

Consider this scenario:

```
ResearchAgent writes: ctx.unified_truth_document
CopywritingAgent writes: ctx.generated_content
CriticAgent READS: ctx.unified_truth_document (allowed)
ModeratorAgent READS: ctx.unified_truth_document (allowed by code, but Moderator depends on Critic, not Research)
```

The ModeratorAgent depends only on CriticAgent, but it can read `ctx.unified_truth_document` which was written by ResearchAgent. If the data contract between Research and Copywriting changes (e.g., `unified_truth_document` is renamed to `utd`), the ModeratorAgent silently breaks even though it has no declared dependency on ResearchAgent.

The dependency graph should enforce data-access boundaries, but it doesn't.

### 4.3 No Agent-to-Agent Messaging

The current architecture prevents several powerful multi-agent patterns:

- **Negotiation**: Critic rejects content → Copywriter rewrites → Critic rejects again. Today this is a loop inside the critic service (`critic_loop.py`), not a multi-agent negotiation. There's no way for the Copywriter to "argue" its case back to the Critic.

- **Partial streaming**: Agent A could send partial results to Agent B while continuing work. With shared context, either A has fully completed or it hasn't — there's no in-between.

- **Consensus building**: Two agents could debate and reach a consensus. This would require bidirectional communication, which the DAG's unidirectional flow doesn't support.

- **Task decomposition**: A supervisor agent could ask sub-agents for status updates, reassign work, or change priorities mid-execution. The static DAG doesn't support this.

---

## 5. Agent Identity & Memory

### 5.1 No Persistent Memory Between Runs

Each pipeline invocation starts with a fresh `AgentContext`. This means:

- **No learning from critic rejections**: If the critic consistently rejects LinkedIn posts for having too many hashtags, the Copywriting agent never learns this. The same rejection patterns repeat across runs.
- **No cross-session brand voice consistency**: The `brand_voice` parameter is passed as a string each time, but there's no mechanism to learn from previous runs about what tone/per-sonality works for a specific brand.
- **No user preference learning**: If a user consistently re-generates content because the tone is wrong, the system doesn't adapt.

### 5.2 Memory Inconsistency Across Agents

The `VoiceProxyAgent` has memory capability (pgvector retrieval for RAG during calls), but the content-manufacturing agents (Research, Copywriting, Critic) have none. This inconsistency means:

- The voice agent can recall past conversations and corporate knowledge
- The manufacturing agents cannot recall past content or past critic feedback for the same client
- If a client says "last time you generated content with too much fluff," the system has no way to adapt based on that memory

### 5.3 No Pipeline Checkpointing

If the server restarts mid-pipeline, all in-flight work is lost. The Redis task queue exists (`redis_queue.py`) but is not integrated with the DAG execution. Proper checkpointing would:

- Persist `AgentContext` to Redis after each successful agent
- On restart, reconstruct the context and resume from the last completed agent
- Track agent execution state in a durable store (Redis, Postgres)

---

## 6. Error Handling & Recovery Patterns

### 6.1 Partial Context on Failure — Broken by Design

When an agent exhausts retries, `orchestrator.py:142-143` raises the exception. The `run()` method exits without returning `ctx`. The caller receives nothing but the exception. If the caller wants the partial context (with results from already-completed agents), it has no way to access it because `ctx` is a local variable in `run()`.

Even if the context were recoverable, there's a second-order problem: the `AgentContext` would contain partial data (e.g., `unified_truth_document` populated but `generated_content` empty). The `ContentResponse` model doesn't allow optional fields, so validating this as a response would fail with a Pydantic error.

The actual route (`content_manufacturing.py`) bypasses the orchestrator entirely and doesn't have this problem — but that means the error-handling infrastructure is completely unused.

### 6.2 Healing Logic Is a Misnomer

`AgentStatus.HEALING` is set during retries but there is no healing logic — just a sleep followed by a blind retry. True healing would involve:

1. **Error classification**: Is this a model error (bad response), an API error (timeout, rate limit), or a validation error (bad contract)?
2. **Strategy selection**: For model errors → change the prompt. For API errors → wait longer or try a fallback model. For validation errors → clamp the data and retry.
3. **Incident reporting**: Log the error type and correction strategy for observability.

### 6.3 No Agent Timeout

The `orchestrator.py:127` retry loop has no timeout enforcement per agent. If `agent.run(ctx)` hangs (e.g., the HTTP client inside the service has a long timeout), the orchestrator hangs indefinitely. The only timeout is `settings.request_timeout_seconds` on the `httpx.AsyncClient` inside each service call, which is:

- Not uniformly configured across services
- Not cancellable at the orchestrator level
- Not visible in the agent's execution span

The orchestrator should wrap each agent's `run()` call with `asyncio.wait_for(agent.run(ctx), timeout=agent_timeout)`.

### 6.4 Circuit Breaker Is Dead Code

The `CircuitBreaker` class (`app/core/circuit_breaker.py`) is well-implemented but **never imported or used by any service**:

- `gemini_grounding.py` — no circuit breaker
- `openrouter_generator.py` — no circuit breaker
- `critic_loop.py` — no circuit breaker

The architect's report claims "all external tool calls are wrapped by the CircuitBreaker" but this is false. Every HTTP call to Gemini, OpenRouter, and the critic model is unprotected.

---

## 7. MCP (Model Context Protocol) Readiness

### 7.1 Service Layer Is the Right Abstraction, but Not MCP-Compliant

The service layer separates agent logic from model calls, which is architecturally sound. However, it doesn't implement MCP:

| MCP Requirement | Current Status |
|----------------|----------------|
| Tool registry with capabilities | Not implemented |
| Standardized tool discovery | Not implemented |
| Access control per tool | Not implemented |
| Streaming tool results | Not implemented |
| Resource templates | Not implemented |

### 7.2 No General Tool-Use Abstraction

Only the Research Agent uses tools (`googleSearch`). The Copywriting Agent and Critic Agent use raw API calls to OpenRouter. The Moderator Agent uses Python regex — which is not a "tool" in the model-sense but a hardcoded rule set.

There is no:
- `Tool` base class or protocol
- Tool registration mechanism
- Tool permission system (which agents can call which tools)
- Tool execution tracing (beyond generic OpenTelemetry spans)

### 7.3 ModeratorAgent Is a Hybrid Anti-Pattern

The ModeratorAgent uses regex patterns, not a model. This means:
- It can't understand context (e.g., "kill" in "this feature will kill the competition" vs. "we will kill them")
- It produces false positives that can't be reasoned about
- It's not swappable — a model-based moderator could be replaced with a different model; the regex moderator requires code changes

---

## 8. Comparison with Industry Frameworks

### 8.1 LangGraph

**Would provide:** Built-in state management with reducers (immutable state transitions), conditional edges (e.g., "if critic rejects, loop back to copywriter"), human-in-the-loop via `interrupt_after`, checkpointing with `MemorySaver`/`SqliteSaver`, and streaming of agent outputs.

**What GNONE would lose:** The simple dataclass-based context would be replaced by LangGraph's `State` with `add_messages` reducer. Some boilerplate for agent node functions. But all of the hand-rolled retry logic, status tracking, and dependency management would be free.

**Migration effort:** Moderate. Each agent becomes a LangGraph node function. The critic loop becomes a `@graph.conditonal_edge`. The context becomes a typed `State` model.

### 8.2 AutoGen (v0.4+)

**Would provide:** Built-in agent-to-agent conversation patterns, `GroupChat` for multi-agent debates, `ToolAgent` for function calling, `UserProxyAgent` for human handoff.

**What GNONE would lose:** The DAG model is flatter than AutoGen's conversation model. AutoGen agents can talk to each other bidirectionally, which the DAG doesn't support.

**Best for:** The critic-copywriter loop could be a two-agent conversation. The moderator could be a registered tool. The voice agent could be an AutoGen agent with a custom WebSocket transport.

### 8.3 CrewAI

**Would provide:** Role-based agent definitions with `role`, `goal`, `backstory` — which GNONE manually implements via class names and docstrings. Built-in task delegation, sequential and hierarchical processes.

**What GNONE would lose:** CrewAI's "sequential" process would map 1:1 to the current linear pipeline. The "hierarchical" process with a manager agent matches the SupervisorAgent described in the roadmap.

### 8.4 Recommendation

**Do not migrate yet.** The current system is too simple (sequential pipeline with 4 agents) to justify the dependency cost of a framework. Migrate when:

1. The system reaches 8+ agents (the roadmap mentions Phase 2)
2. The system needs bidirectional agent communication (critic-copywriter debate, supervisor delegation)
3. The system needs human-in-the-loop approval gates (mentioned in the roadmap)
4. The team needs debugging/tracing tools beyond what OpenTelemetry provides

**When that happens, prefer LangGraph over AutoGen or CrewAI** because:
- LangGraph's explicit graph model maps directly to the current DAG concept
- Conditional edges map to the critic approval/regeneration branch
- Checkpointing is built-in and would solve the mid-pipeline restart problem
- It has the best production-grade persistence story

---

## 9. Critical Bugs

### B1: The Orchestrator Is Dead Code (DOCUMENTATION ≠ IMPLEMENTATION)

**File:** `app/routes/content_manufacturing.py:64-105`
**Issue:** The API route does NOT use `DAGOrchestrator`, `BaseAgent`, or any of the agent classes. It directly calls `research_topic()`, `generate_platform_content()`, and `critic_verification_loop()` as independent functions. The `DAGOrchestrator` at `orchestrator.py:84`, all five agent classes, and the entire `AgentContext`/`AgentNode`/`AgentStatus` infrastructure are unreachable code.

**Impact:** Every design claim in the architect's report about the orchestrator is false. The retry logic, status tracking, circuit breaker integration, dependency management, and parallel execution capabilities documented in the report do not exist in the running system. The actual system is a hardcoded sequential script.

### B2: Circuit Breaker Is Dead Code

**File:** `app/core/circuit_breaker.py` (entire file)
**Issue:** The `CircuitBreaker` class is never imported or instantiated by any service. `gemini_grounding.py`, `openrouter_generator.py`, and `critic_loop.py` all make direct HTTP calls without circuit breaker protection.

**Impact:** If Gemini API goes down, every request to the content manufacturing endpoint will hang for `settings.request_timeout_seconds` (potentially 120s) before failing, repeating this for every request, until the system retries and fails again. The circuit breaker was designed to prevent exactly this scenario.

### B3: CopywritingContract, ModeratorVerdict, DeploymentContract Are Dead Code

**File:** `app/models/agent_contracts.py:30-73`
**Issue:** `CopywritingContract` (line 30), `ModeratorVerdict` (line 57), and `DeploymentContract` (line 66) are defined but never instantiated. The actual data flow uses `MultiPlatformContent` directly for the copywriting → critic boundary, and the ModeratorAgent is never called from the API route.

### B4: No Agent Timeout — Orchestrator Can Hang Indefinitely

**File:** `app/core/orchestrator.py:127-143`
**Issue:** The retry loop has `await agent.run(ctx)` with no `asyncio.wait_for()` wrapper. If the agent's internal HTTP call hangs (e.g., due to a slow API response within the configured timeout), the orchestrator blocks. With 3 retries and a 120s timeout, a single agent can take 360+ seconds.

### B5: Static_order() Prevents Parallelism Even When the Graph Supports It

**File:** `app/core/orchestrator.py:101-103`
**Issue:** `list(ts.static_order())` returns a flat ordered list. True parallel execution requires `ts.get_ready()` + `asyncio.gather()`. The code as written will execute every agent sequentially even if the DAG has independent branches.

### B6: AgentContext Has No `source_domains` Field, but Code Assigns to It

**File:** `app/agents/research_agent.py:25`, `app/core/orchestrator.py:22-34`
**Issue:** `ctx.source_domains = contract.source_domains` assigns to an attribute not defined in the `AgentContext` dataclass. This creates a dynamic attribute on the instance (Python dataclasses don't prevent this), which means `ctx.get("source_domains")` works but `hasattr(fields(ctx).keys(), "source_domains")` would fail. This is fragile and inconsistent with the typed-dataclass pattern used everywhere else.

### B7: critic_loop.py:132-136 Can Validate Corrupted Payloads

**File:** `app/services/critic_loop.py:131-136`
**Issue:** When the critic returns `corrected_payloads` as a non-empty dict, it is validated against `MultiPlatformContent.model_validate()`. If the critic model returns a malformed structure (common with JSON-mode failures), this raises a Pydantic `ValidationError`, which propagates up to the retry loop. The retry loop retries with the SAME input, getting the SAME bad output, burning all 3 retries on a deterministic failure.

### B8: ModeratorAgent Is Never Called

**File:** `app/routes/content_manufacturing.py` (entire file)
**Issue:** The `ModeratorAgent` class is defined at `moderator_agent.py:21` but never invoked from the API route or the DAGOrchestrator. Content leaves the system without any content-safety moderation.

### B9: `target_platforms` Field Is Accepted but Ignored

**File:** `app/schemas.py:18-21`, `app/routes/content_manufacturing.py`
**Issue:** `ContentRequest.target_platforms` is a user-facing field that accepts a list of platforms (defaulting to all four). The API route ignores this field entirely — it always generates content for all four platforms. If a user sends `target_platforms: ["twitter"]`, they receive all platforms.

### B10: Except Overflow — Critic Loop Catches Wrong Exception Layer

**File:** `app/agents/critic_agent.py:22-38`
**Issue:** The critic agent catches only `MaxRetriesExceededError`. If `MultiPlatformContent.model_validate(ctx.generated_content)` at line 20 raises a `ValidationError` (e.g., because the copywriter produced truncated JSON), the exception is NOT caught here. It propagates to the orchestrator's retry loop (line 132), which retries the entire critic agent. But the input data is the same, so the retries all fail deterministically.

Meanwhile, in `critic_loop.py:132-136`, the same `model_validate` on `corrected_payloads` can also fail with a `ValidationError`, which propagates out of `critic_verification_loop()` and is caught by... the route's `@catch_malformed_json` decorator, which returns a 422. The critic agent is not involved.

---

## 10. Recommendations

### P0 — Ship-Blocking (Address Before Next Deployment)

**R1: Remove or Integrate the Dead Orchestrator Code**

Either: (a) Integrate the actual API route with the DAGOrchestrator, making the route call `orchestrator.run()` with registered agents, which would give you retry logic, status tracking, and error propagation for free; or (b) Delete the DAGOrchestrator, all agent classes, AgentStatus, AgentNode, and AgentContext, and rename the route's direct-service-call pattern to something honest like `ContentPipeline`.

**Files affected:** `app/core/orchestrator.py`, `app/agents/*.py`, `app/routes/content_manufacturing.py`

**R2: Wire the Circuit Breaker into All Service Calls**

Add `circuit_breaker.call()` wrappers around the HTTP calls in `gemini_grounding.py`, `openrouter_generator.py`, and `critic_loop.py`. Create one `CircuitBreaker` instance per service (e.g., `CircuitBreaker("gemini")`, `CircuitBreaker("openrouter")`).

**Files affected:** `app/services/gemini_grounding.py:67`, `app/services/openrouter_generator.py:72`, `app/services/critic_loop.py:78`

**R3: Integrate the ModeratorAgent into the Pipeline**

Either call it from the route after the critic succeeds, or (better) integrate it into the DAGOrchestrator flow. Currently content exits the system with zero safety moderation.

**Files affected:** `app/routes/content_manufacturing.py` (add moderator step)

### P1 — Important (Address Within 2 Sprints)

**R4: Add Agent Timeout to the Orchestrator**

Wrap each agent execution with `asyncio.wait_for(agent.run(ctx), timeout=max_agent_timeout)`. Configure the timeout per agent (e.g., ResearchAgent = 60s, CopywritingAgent = 90s, CriticAgent = 120s).

```python
try:
    ctx = await asyncio.wait_for(
        agent.run(ctx), timeout=settings.agent_timeout_seconds
    )
except asyncio.TimeoutError:
    raise ModelTimeoutError(f"Agent '{agent_name}' timed out")
```

**Files affected:** `app/core/orchestrator.py:129`

**R5: Replace Shared Mutable Context with Message-Passing**

Introduce a `MessageBus` abstraction where agents send and receive typed messages:

```python
class MessageBus:
    async def send(self, to: str, message: BaseModel): ...
    async def receive(self, agent_name: str, timeout: float) -> list[Message]: ...
    def snapshot(self) -> list[Message]: ...  # for checkpointing
```

Each agent declares the message types it sends and receives. The orchestrator routes messages between agents based on the dependency graph. This enables auditability, isolation, and crash containment.

**Files affected:** `app/core/orchestrator.py`, all agent files, new `app/core/message_bus.py`

### P2 — Nice to Have (Address When Resources Permit)

**R6: Add Pipeline Checkpointing via Redis**

After each agent completes successfully, persist a serialized snapshot of `AgentContext` (or the message bus state) to Redis. On server restart, check for an in-progress pipeline and resume from the last checkpoint. The existing `redis_queue.py` infrastructure can be extended for this.

**R7: Introduce a General Tool Abstraction**

Create a `Tool` base class that all tools (Google Search, OpenRouter model calls, regex scanning, pgvector retrieval) implement:

```python
class Tool(ABC):
    name: str
    description: str
    parameters: type[BaseModel]
    @abstractmethod
    async def run(self, **kwargs) -> Any: ...
```

Register tools in a global `ToolRegistry`. Agents declare which tools they need. The circuit breaker and rate limiter wrap at the tool level. This prepares the architecture for MCP compliance and makes the ModeratorAgent's regex patterns a tool that could be swapped for an LLM-based moderator.

**R8: Add Active Healing Logic to the Retry Loop**

Replace the blind retry (`asyncio.sleep; retry with same inputs`) with actual healing:

```python
match type(error):
    case ModelTimeoutError():
        await asyncio.sleep(2.0 * attempt)  # longer wait
    case ModelRateLimitError():
        await asyncio.sleep(error.retry_after)  # respect Retry-After
    case ValidationError():
        # try with a different model or prompt variant
        agent.use_fallback_prompt()
    case CircuitBreakerOpen():
        raise  # don't retry, the breaker will probe
```

**R9: Add Memory to the Manufacturing Agents**

Store critic rejection patterns, approved content samples, and brand voice adjustments in a vector store (pgvector, same as the voice agent). On each pipeline start, retrieve relevant memories for the client/brand and inject them into the agent prompts via RAG.

**R10: Immutable State with Message History**

Replace the mutable `AgentContext` with an immutable `PipelineState` backed by a list of `StateEvent`:

```python
@dataclass
class StateEvent:
    agent: str
    timestamp: datetime
    event_type: Literal["output", "error", "metric"]
    payload: BaseModel

class PipelineState:
    _events: list[StateEvent]
    def latest(self, agent: str) -> Optional[BaseModel]: ...
    def search(self, **filters) -> list[StateEvent]: ...
```

This gives you a complete, immutable audit trail of every agent interaction, which can be replayed, debugged, or analyzed post-hoc.

---

## Summary

GNONE's agent architecture has the **right ideas** — typed contracts, service-layer isolation, observability — but the **execution is broken at the integration layer**. The orchestrator is unused, the circuit breaker is dead, the moderator is bypassed, and the contract system is partially dead code. The documented architecture is a fiction; the running system is a hardcoded sequential script.

The system does not need a framework migration yet (it's too simple), but it does need: (1) integration of the existing infrastructure that was built but never wired up, (2) replacement of shared mutable state with message-passing before the system grows to 8+ agents, and (3) honest documentation that matches the implementation.

The score of 4.5/10 reflects that the *individual pieces* are well-architected but the *system as a whole* does not function as described and has critical operational gaps (no circuit breaker, no timeout enforcement, no moderation, dead code paths).
