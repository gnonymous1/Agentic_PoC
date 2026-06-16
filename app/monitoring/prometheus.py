"""
Prometheus metric definitions for the GNONE platform.
These align with the MetricsRegistry in core/metrics.py and are
exposed via the /metrics endpoint for Prometheus scraping.
"""

from app.core.metrics import registry

# ── Request-level counters ──────────────────────────────────────────────────

def inc_requests_total(model: str, status: str):
    registry.increment("gnone_requests_total", {"model": model, "status": status})


def inc_content_pieces_total(platform: str):
    registry.increment("gnone_content_pieces_total", {"platform": platform})


def inc_critic_cycles_total(result: str):
    registry.increment("gnone_critic_cycles_total", {"result": result})


# ── Latency histograms ─────────────────────────────────────────────────────

def record_research_latency(seconds: float):
    registry.histogram("gnone_research_latency_seconds").record(seconds)


def record_generation_latency(seconds: float):
    registry.histogram("gnone_generation_latency_seconds").record(seconds)


def record_critic_latency(seconds: float):
    registry.histogram("gnone_critic_latency_seconds").record(seconds)


def record_pipeline_latency(seconds: float):
    registry.histogram("gnone_pipeline_latency_seconds").record(seconds)


# ── Business metrics ────────────────────────────────────────────────────────

def inc_revenue_closed(amount: float):
    registry.increment("gnone_revenue_closed_total")
    # Track as histogram for distribution analysis
    registry.histogram("gnone_deal_value").record(amount)


def record_refinement_cycles(cycles: int):
    registry.histogram("gnone_refinement_cycles").record(float(cycles))


# ── Error tracking ──────────────────────────────────────────────────────────

def inc_errors_total(error_type: str):
    registry.increment("gnone_errors_total", {"type": error_type})
