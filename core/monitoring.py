import time
import json
import asyncio
import uuid
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class MetricPoint:
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class SpanTrace:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    agent: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "running"
    metadata: dict = field(default_factory=dict)
    children: List["SpanTrace"] = field(default_factory=list)
    error: Optional[str] = None

class CostTracker:
    """Track LLM API costs in real-time."""

    def __init__(self):
        self.daily_costs: Dict[str, float] = defaultdict(float)
        self.per_provider_costs: Dict[str, float] = defaultdict(float)
        self.per_agent_costs: Dict[str, float] = defaultdict(float)
        self.per_task_costs: Dict[str, float] = defaultdict(float)
        self.cost_history: List[dict] = []

    def record_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
        agent: str = "unknown",
        task_type: str = "unknown"
    ):
        cost = (
            (input_tokens / 1000) * cost_per_1k_input +
            (output_tokens / 1000) * cost_per_1k_output
        )

        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_costs[today] += cost
        self.per_provider_costs[provider] += cost
        self.per_agent_costs[agent] += cost
        self.per_task_costs[task_type] += cost

        self.cost_history.append({
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
            "agent": agent,
            "task_type": task_type,
        })

    def get_daily_spend(self) -> float:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.daily_costs.get(today, 0.0)

    def get_cost_report(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "today_usd": round(self.daily_costs.get(today, 0.0), 4),
            "by_provider": dict(self.per_provider_costs),
            "by_agent": dict(self.per_agent_costs),
            "by_task": dict(self.per_task_costs),
            "total_all_time": round(sum(self.daily_costs.values()), 4),
            "last_10_calls": self.cost_history[-10:],
        }

class PerformanceTracker:
    """Track performance across all dimensions."""

    def __init__(self):
        self.response_times: Dict[str, List[float]] = defaultdict(list)
        self.throughput: Dict[str, int] = defaultdict(int)

    def record_response_time(self, agent: str, action: str, duration_ms: float):
        key = f"{agent}.{action}"
        self.response_times[key].append(duration_ms)
        self.throughput[key] += 1

        # Keep last 1000 per key
        if len(self.response_times[key]) > 1000:
            self.response_times[key] = self.response_times[key][-1000:]

    def get_slow_operations(self, threshold_ms: float = 5000) -> List[dict]:
        """Find operations that are consistently slow."""
        slow = []
        for key, times in self.response_times.items():
            if len(times) >= 5:
                avg = statistics.mean(times)
                if avg > threshold_ms:
                    slow.append({
                        "operation": key,
                        "avg_ms": round(avg),
                        "p95_ms": round(sorted(times)[int(len(times) * 0.95)]),
                        "count": len(times),
                    })
        return sorted(slow, key=lambda x: x["avg_ms"], reverse=True)
        
    def get_performance_score(self) -> dict:
        """Overall system performance score 0-100."""
        scores = []
        for key, times in self.response_times.items():
            if len(times) >= 1:
                avg = statistics.mean(times)
                if avg < 1000:
                    scores.append(100)
                elif avg < 3000:
                    scores.append(70)
                elif avg < 10000:
                    scores.append(40)
                else:
                    scores.append(10)

        return {
            "overall_score": round(statistics.mean(scores)) if scores else 0,
            "total_operations": sum(self.throughput.values()),
            "slow_operations": len(self.get_slow_operations()),
        }

class AnomalyDetector:
    """Detect unusual patterns in system behavior."""

    def __init__(self):
        self.baselines: Dict[str, dict] = {}
        self.anomalies: List[dict] = []

    def check(self, span: SpanTrace):
        """Check if a span's metrics are anomalous."""
        if not span.end_time:
            return

        duration = (span.end_time - span.start_time) * 1000
        key = f"{span.agent}.{span.operation}"

        # Build baseline
        if key not in self.baselines:
            self.baselines[key] = {
                "durations": [],
                "error_count": 0,
                "total_count": 0
            }

        baseline = self.baselines[key]
        baseline["total_count"] += 1
        baseline["durations"].append(duration)

        if span.status == "error":
            baseline["error_count"] += 1

        # Need enough data for baseline
        if baseline["total_count"] < 10:
            return

        # Check duration anomaly (> 3 standard deviations)
        durations = baseline["durations"][-100:]
        mean = statistics.mean(durations)
        stdev = statistics.stdev(durations) if len(durations) > 1 else 0

        if stdev > 0 and duration > mean + (3 * stdev):
            self.anomalies.append({
                "type": "slow_execution",
                "agent": span.agent,
                "operation": span.operation,
                "duration_ms": round(duration),
                "baseline_mean_ms": round(mean),
                "baseline_stdev_ms": round(stdev),
                "deviation": round((duration - mean) / stdev, 1),
                "timestamp": datetime.now().isoformat(),
            })

    def get_recent_anomalies(self, hours: int = 24) -> List[dict]:
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            a for a in self.anomalies
            if datetime.fromisoformat(a["timestamp"]) > cutoff
        ]

class ObservabilityEngine:
    """
    Complete observability for every operation in OMNIOS.
    Tracks: Metrics, Traces, Logs, Cost, Performance, Patterns
    """

    def __init__(self, config: dict):
        self.config = config
        self.metrics: List[MetricPoint] = []
        self.traces: Dict[str, SpanTrace] = {}
        self.cost_tracker = CostTracker()
        self.performance_tracker = PerformanceTracker()
        self.anomaly_detector = AnomalyDetector()
        self.dashboards = DashboardDataProvider(self)

    # ================================================
    # DISTRIBUTED TRACING — Trace every request end-to-end
    # ================================================

    def start_trace(
        self,
        operation: str,
        agent: str = "coordinator",
        parent_trace_id: str = None,
        metadata: dict = None
    ) -> SpanTrace:
        """Start a new trace span for any operation."""
        trace_id = parent_trace_id or str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        span = SpanTrace(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_trace_id,
            operation=operation,
            agent=agent,
            start_time=time.time(),
            metadata=metadata or {},
        )

        self.traces[span_id] = span

        # Link to parent span
        if parent_trace_id and parent_trace_id in self.traces:
            self.traces[parent_trace_id].children.append(span)

        return span

    def end_trace(
        self,
        span: SpanTrace,
        status: str = "success",
        error: str = None,
        result_metadata: dict = None
    ):
        """End a trace span."""
        span.end_time = time.time()
        span.status = status
        span.error = error
        if result_metadata:
            span.metadata.update(result_metadata)

        # Calculate duration
        duration_ms = (span.end_time - span.start_time) * 1000

        # Record metrics
        self.record_metric(
            f"agent.{span.agent}.duration_ms",
            duration_ms,
            tags={"operation": span.operation, "status": status}
        )

        self.performance_tracker.record_response_time(span.agent, span.operation, duration_ms)

        if status == "error":
            self.record_metric(
                f"agent.{span.agent}.errors",
                1,
                tags={"operation": span.operation, "error_type": error or "unknown"}
            )

        # Check for anomalies
        self.anomaly_detector.check(span)

    # ================================================
    # METRICS COLLECTION
    # ================================================

    def record_metric(
        self,
        name: str,
        value: float,
        tags: dict = None
    ):
        self.metrics.append(MetricPoint(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {}
        ))

        # Keep only last 24h of metrics in memory
        cutoff = time.time() - 86400
        self.metrics = [m for m in self.metrics if m.timestamp > cutoff]

    def get_metrics_summary(
        self,
        name_prefix: str = "",
        hours: int = 24
    ) -> dict:
        """Get aggregated metrics with percentiles."""
        cutoff = time.time() - (hours * 3600)
        relevant = [
            m for m in self.metrics
            if m.timestamp > cutoff and m.name.startswith(name_prefix)
        ]

        if not relevant:
             return {}

        grouped = defaultdict(list)
        for m in relevant:
            grouped[m.name].append(m.value)

        summary = {}
        for name, values in grouped.items():
            summary[name] = {
                "count": len(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "p95": self._percentile(values, 95),
                "p99": self._percentile(values, 99),
                "min": min(values),
                "max": max(values),
                "sum": sum(values),
            }

        return summary

    def _percentile(self, values: list, p: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        idx = max(0, int(len(sorted_vals) * p / 100) - 1)
        return sorted_vals[idx]


class DashboardDataProvider:
    """Aggregate data for real-time dashboard."""

    def __init__(self, observability: ObservabilityEngine):
        self.obs = observability

    def get_realtime_dashboard(self) -> dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "performance": self.obs.performance_tracker.get_performance_score(),
            "costs": self.obs.cost_tracker.get_cost_report(),
            "anomalies": self.obs.anomaly_detector.get_recent_anomalies(1),
            "slow_operations": self.obs.performance_tracker.get_slow_operations(),
            "active_traces": len([
                t for t in self.obs.traces.values()
                if t.status == "running"
            ]),
        }
