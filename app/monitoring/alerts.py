"""
Alert rule definitions for the GNONE platform.
These map to Prometheus alerting rules or external PagerDuty/Opsgenie integrations.
"""

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AlertRule:
    name: str
    description: str
    severity: Severity
    condition: str
    duration: str = "5m"
    annotations: dict = None


CRITICAL_ALERTS = [
    AlertRule(
        name="HighErrorRate",
        description="Error rate exceeds 5% over 5 minutes",
        severity=Severity.CRITICAL,
        condition="rate(gnone_errors_total[5m]) / rate(gnone_requests_total[5m]) > 0.05",
    ),
    AlertRule(
        name="PipelineLatencyHigh",
        description="P95 pipeline latency exceeds 120 seconds",
        severity=Severity.CRITICAL,
        condition="histogram_quantile(0.95, rate(gnone_pipeline_latency_seconds_bucket[5m])) > 120",
    ),
    AlertRule(
        name="CircuitBreakerOpen",
        description="Circuit breaker open for 10+ minutes",
        severity=Severity.CRITICAL,
        condition="gnone_circuit_breaker_state{state='open'} > 600",
    ),
]

WARNING_ALERTS = [
    AlertRule(
        name="RefinementCycleBudget",
        description="Content requiring 3+ critic refinement cycles",
        severity=Severity.WARNING,
        condition="rate(gnone_refinement_cycles_bucket{le='3'}[15m]) < 0.8",
    ),
    AlertRule(
        name="CriticRejectionSpike",
        description="Critic rejection rate exceeds 30% over 15 minutes",
        severity=Severity.WARNING,
        condition="rate(gnone_critic_cycles_total{result='rejected'}[15m]) / rate(gnone_critic_cycles_total[15m]) > 0.3",
    ),
    AlertRule(
        name="TokenExceededWarning",
        description="Token usage approaching 80% of daily quota for a client",
        severity=Severity.WARNING,
        condition="gnone_client_token_usage / gnone_client_token_quota > 0.8",
    ),
]
