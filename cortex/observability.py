"""
Observability Engine
Provides comprehensive monitoring, metrics, tracing, and alerting for AgentOS.
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
from cortex.events import EventBus, EventType


class LogLevel(Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Status(Enum):
    """Operation status."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


@dataclass
class TraceContext:
    """Context for distributed tracing."""
    trace_id: str
    operation: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: Status = Status.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    spans: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Alert:
    """Alert definition."""
    alert_id: str
    name: str
    severity: str  # "info", "warning", "critical"
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


class ObservabilityEngine:
    """
    Comprehensive observability engine for AgentOS.
    """
    
    def __init__(self):
        self.event_bus = EventBus.get_sync()
        
        # Metrics storage
        self.metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.metric_aggregates: Dict[str, Dict[str, float]] = {}
        
        # Tracing
        self.active_traces: Dict[str, TraceContext] = {}
        self.completed_traces: List[TraceContext] = []
        self.max_completed_traces = 1000
        
        # Logging
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 10000
        
        # Alerting
        self.alerts: List[Alert] = []
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.performance_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_duration": 0.0
        }
        
        self._initialize_alert_rules()
    
    def _initialize_alert_rules(self):
        """Initialize default alert rules."""
        self.alert_rules = {
            "high_error_rate": {
                "threshold": 0.1,  # 10% error rate
                "window": 300,  # 5 minutes
                "severity": "warning"
            },
            "slow_response": {
                "threshold": 10.0,  # 10 seconds
                "severity": "warning"
            },
            "critical_error": {
                "severity": "critical"
            }
        }
    
    def record_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Optional tags for filtering
        """
        metric_entry = {
            "name": name,
            "value": value,
            "timestamp": time.time(),
            "tags": tags or {}
        }
        
        self.metrics[name].append(metric_entry)
        
        # Update aggregates
        if name not in self.metric_aggregates:
            self.metric_aggregates[name] = {
                "count": 0,
                "sum": 0.0,
                "min": float('inf'),
                "max": float('-inf'),
                "avg": 0.0
            }
        
        agg = self.metric_aggregates[name]
        agg["count"] += 1
        agg["sum"] += value
        agg["min"] = min(agg["min"], value)
        agg["max"] = max(agg["max"], value)
        agg["avg"] = agg["sum"] / agg["count"]
        
        # Emit metric event
        self.event_bus.emit_sync(
            EventType.SYSTEM_EVENT,
            {
                "action": "metric_recorded",
                "metric": name,
                "value": value,
                "tags": tags
            },
            source="observability"
        )
    
    def start_trace(self, operation: str, metadata: Optional[Dict[str, Any]] = None) -> TraceContext:
        """
        Start a new trace.
        
        Args:
            operation: Operation name
            metadata: Optional metadata
            
        Returns:
            TraceContext object
        """
        import uuid
        trace_id = str(uuid.uuid4())[:8]
        
        context = TraceContext(
            trace_id=trace_id,
            operation=operation,
            metadata=metadata or {}
        )
        
        self.active_traces[trace_id] = context
        
        self.log(LogLevel.DEBUG, f"Started trace: {operation}", {"trace_id": trace_id})
        
        return context
    
    def end_trace(self, context: TraceContext, status: Status):
        """
        End a trace.
        
        Args:
            context: Trace context
            status: Final status
        """
        context.end_time = time.time()
        context.status = status
        
        duration = context.end_time - context.start_time
        
        # Record metrics
        self.record_metric(f"trace.{context.operation}.duration", duration)
        self.record_metric(f"trace.{context.operation}.count", 1, {"status": status.value})
        
        # Move to completed traces
        if context.trace_id in self.active_traces:
            del self.active_traces[context.trace_id]
        
        self.completed_traces.append(context)
        
        # Limit completed traces
        if len(self.completed_traces) > self.max_completed_traces:
            self.completed_traces = self.completed_traces[-self.max_completed_traces:]
        
        self.log(
            LogLevel.DEBUG,
            f"Ended trace: {context.operation} ({status.value}, {duration:.2f}s)",
            {"trace_id": context.trace_id}
        )
    
    def log(self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Log a message.
        
        Args:
            level: Log level
            message: Log message
            context: Optional context data
        """
        log_entry = {
            "level": level.value,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "context": context or {}
        }
        
        self.logs.append(log_entry)
        
        # Limit logs
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
        
        # Print to console
        print(f"[{level.value}] {message}")
        
        # Check for alert conditions
        if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            self._check_error_alerts(message, level, context)
    
    def check_alerts(self) -> List[Alert]:
        """
        Check for alert conditions.
        
        Returns:
            List of active alerts
        """
        new_alerts = []
        
        # Check error rate
        error_rate = self._calculate_error_rate()
        if error_rate > self.alert_rules["high_error_rate"]["threshold"]:
            alert = Alert(
                alert_id=f"error_rate_{int(time.time())}",
                name="High Error Rate",
                severity="warning",
                message=f"Error rate is {error_rate:.1%} (threshold: {self.alert_rules['high_error_rate']['threshold']:.1%})",
                timestamp=datetime.now(),
                metadata={"error_rate": error_rate}
            )
            new_alerts.append(alert)
            self.alerts.append(alert)
        
        # Check slow responses
        slow_traces = [
            t for t in self.completed_traces[-100:]
            if t.end_time and (t.end_time - t.start_time) > self.alert_rules["slow_response"]["threshold"]
        ]
        
        if slow_traces:
            alert = Alert(
                alert_id=f"slow_response_{int(time.time())}",
                name="Slow Response Detected",
                severity="warning",
                message=f"{len(slow_traces)} slow responses detected",
                timestamp=datetime.now(),
                metadata={"slow_traces": len(slow_traces)}
            )
            new_alerts.append(alert)
            self.alerts.append(alert)
        
        return new_alerts
    
    def get_metrics(self, name: Optional[str] = None, window: Optional[int] = None) -> Dict[str, Any]:
        """
        Get metrics.
        
        Args:
            name: Specific metric name (None for all)
            window: Time window in seconds (None for all time)
            
        Returns:
            Metrics data
        """
        if name:
            if name not in self.metrics:
                return {"error": "Metric not found"}
            
            metrics = self.metrics[name]
            
            # Apply time window
            if window:
                cutoff = time.time() - window
                metrics = [m for m in metrics if m["timestamp"] >= cutoff]
            
            return {
                "name": name,
                "data_points": len(metrics),
                "aggregates": self.metric_aggregates.get(name, {}),
                "recent": metrics[-10:]  # Last 10 values
            }
        else:
            return {
                "metrics": list(self.metrics.keys()),
                "total_data_points": sum(len(m) for m in self.metrics.values()),
                "aggregates": self.metric_aggregates
            }
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get trace details."""
        # Check active traces
        if trace_id in self.active_traces:
            context = self.active_traces[trace_id]
            return {
                "trace_id": context.trace_id,
                "operation": context.operation,
                "status": context.status.value,
                "duration": time.time() - context.start_time if not context.end_time else context.end_time - context.start_time,
                "metadata": context.metadata,
                "spans": context.spans
            }
        
        # Check completed traces
        for context in self.completed_traces:
            if context.trace_id == trace_id:
                return {
                    "trace_id": context.trace_id,
                    "operation": context.operation,
                    "status": context.status.value,
                    "duration": context.end_time - context.start_time if context.end_time else None,
                    "metadata": context.metadata,
                    "spans": context.spans
                }
        
        return None
    
    def query_logs(
        self,
        level: Optional[LogLevel] = None,
        search: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query logs.
        
        Args:
            level: Filter by log level
            search: Search in message
            limit: Maximum results
            
        Returns:
            List of log entries
        """
        logs = self.logs
        
        # Filter by level
        if level:
            logs = [log for log in logs if log["level"] == level.value]
        
        # Search in message
        if search:
            logs = [log for log in logs if search.lower() in log["message"].lower()]
        
        # Return most recent
        return logs[-limit:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = self.performance_stats.copy()
        
        # Calculate derived metrics
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["failure_rate"] = stats["failed_requests"] / stats["total_requests"]
            stats["avg_duration"] = stats["total_duration"] / stats["total_requests"]
        else:
            stats["success_rate"] = 0.0
            stats["failure_rate"] = 0.0
            stats["avg_duration"] = 0.0
        
        return stats
    
    def _calculate_error_rate(self, window: int = 300) -> float:
        """Calculate error rate over time window."""
        cutoff = time.time() - window
        
        recent_logs = [log for log in self.logs if datetime.fromisoformat(log["timestamp"]).timestamp() >= cutoff]
        
        if not recent_logs:
            return 0.0
        
        error_logs = [log for log in recent_logs if log["level"] in ["ERROR", "CRITICAL"]]
        
        return len(error_logs) / len(recent_logs)
    
    def _check_error_alerts(self, message: str, level: LogLevel, context: Optional[Dict[str, Any]]):
        """Check if error should trigger an alert."""
        if level == LogLevel.CRITICAL:
            alert = Alert(
                alert_id=f"critical_{int(time.time())}",
                name="Critical Error",
                severity="critical",
                message=message,
                timestamp=datetime.now(),
                metadata=context or {}
            )
            self.alerts.append(alert)
            
            # Emit alert event
            self.event_bus.emit_sync(
                EventType.SYSTEM_ERROR,
                {
                    "action": "critical_alert",
                    "message": message,
                    "context": context
                },
                source="observability"
            )
    
    def export_traces(self, filepath: str = "traces.json"):
        """
        Export completed traces to a JSON file in OpenTelemetry-like format.
        """
        otel_traces = []
        for trace in self.completed_traces:
            spans = []
            # root span
            spans.append({
                "traceId": trace.trace_id,
                "spanId": trace.trace_id, # Simplified
                "name": trace.operation,
                "startTimeUnixNano": int(trace.start_time * 1e9),
                "endTimeUnixNano": int(trace.end_time * 1e9) if trace.end_time else None,
                "status": {"code": trace.status.value},
                "attributes": trace.metadata
            })
            # child spans
            for span in trace.spans:
                spans.append({
                    "traceId": trace.trace_id,
                    "spanId": span.get("span_id", "unknown"),
                    "name": span.get("name", "unknown"),
                    "startTimeUnixNano": int(span.get("start_time", 0) * 1e9),
                    "endTimeUnixNano": int(span.get("end_time", 0) * 1e9),
                    "attributes": span.get("metadata", {})
                })
            
            otel_traces.append({
                "resourceSpans": [{
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "agentos"}}]},
                    "scopeSpans": [{"spans": spans}]
                }]
            })
            
        with open(filepath, "w") as f:
            json.dump({"batch": otel_traces}, f, indent=2)
        print(f"[Observability] Exported {len(otel_traces)} traces to {filepath}")


# Global instance
observability_engine = ObservabilityEngine()


def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Record a metric."""
    observability_engine.record_metric(name, value, tags)


def start_trace(operation: str, metadata: Optional[Dict[str, Any]] = None) -> TraceContext:
    """Start a trace."""
    return observability_engine.start_trace(operation, metadata)


def end_trace(context: TraceContext, status: Status):
    """End a trace."""
    observability_engine.end_trace(context, status)


def log(level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None):
    """Log a message."""
    observability_engine.log(level, message, context)


def get_metrics(name: Optional[str] = None, window: Optional[int] = None) -> Dict[str, Any]:
    """Get metrics."""
    return observability_engine.get_metrics(name, window)


def get_trace(trace_id: str) -> Optional[Dict[str, Any]]:
    """Get trace details."""
    return observability_engine.get_trace(trace_id)


def query_logs(
    level: Optional[LogLevel] = None,
    search: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Query logs."""
    return observability_engine.query_logs(level, search, limit)


def check_alerts() -> List[Alert]:
    """Check for alerts."""
    return observability_engine.check_alerts()


def get_performance_stats() -> Dict[str, Any]:
    """Get performance statistics."""
    return observability_engine.get_performance_stats()
