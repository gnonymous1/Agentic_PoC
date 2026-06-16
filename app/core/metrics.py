import time
from contextlib import contextmanager

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, Histogram, generate_latest

requests_total = Counter(
    'gnone_requests_total',
    'Total requests by model and status',
    ['model', 'status'],
)

content_pieces_total = Counter(
    'gnone_content_pieces_total',
    'Content pieces by platform',
    ['platform'],
)

errors_total = Counter(
    'gnone_errors_total',
    'Errors by type',
    ['type'],
)

pipeline_latency = Histogram(
    'gnone_pipeline_latency_seconds',
    'Pipeline latency',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

research_latency = Histogram(
    'gnone_research_latency_seconds',
    'Research latency',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

generation_latency = Histogram(
    'gnone_generation_latency_seconds',
    'Generation latency',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

critic_latency = Histogram(
    'gnone_critic_latency_seconds',
    'Critic latency',
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

refinement_cycles = Histogram(
    'gnone_refinement_cycles',
    'Critic refinement cycles',
    buckets=[1, 2, 3],
)


@contextmanager
def timed(histogram: Histogram, labels: dict | None = None):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        if labels:
            histogram.labels(**labels).observe(elapsed)
        else:
            histogram.observe(elapsed)


def metrics_app():
    from fastapi.responses import Response
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
