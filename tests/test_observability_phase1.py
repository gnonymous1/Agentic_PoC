import asyncio
import time
from core.monitoring import ObservabilityEngine
from monitoring.evolution_metrics import EvolutionMetrics

async def test_observability_flow():
    config = {"providers": {"openai": {"api_key": "test"}}}
    obs = ObservabilityEngine(config)
    evo = EvolutionMetrics(obs)

    print("Testing Trace Flow...")
    root = obs.start_trace("root_op", "test_agent")
    time.sleep(0.1)
    child = obs.start_trace("child_op", "test_subagent", parent_trace_id=root.span_id)
    time.sleep(0.2)
    obs.end_trace(child, status="success")
    obs.end_trace(root, status="success")

    print(f"Root Span status: {root.status}")
    print(f"Child Span count in root: {len(root.children)}")
    if len(root.children) == 1 and root.children[0].span_id == child.span_id:
        print("PASS: Span linking verified")
    else:
        print("FAIL: Span linking failed")

    print("\nTesting Metrics & Percentiles...")
    for i in range(1, 101):
        obs.record_metric("test.latency", float(i))
    
    summary = obs.get_metrics_summary("test.latency")
    latency_stats = summary.get("test.latency", {})
    print(f"Latency Summary: {latency_stats}")
    
    if latency_stats.get("p95") == 95.0 and latency_stats.get("p99") == 99.0:
        print("PASS: Percentile calculation verified")
    else:
        print(f"FAIL: Percentile mismatch (p95={latency_stats.get('p95')}, p99={latency_stats.get('p99')})")

    print("\nTesting Dashboard...")
    dashboard = obs.dashboards.get_realtime_dashboard()
    print(f"Dashboard Keys: {list(dashboard.keys())}")
    print(f"Performance Score: {dashboard['performance']}")

    print("\nTesting Evolution Metrics...")
    report = evo.get_evolution_report()
    print(f"Evolution Report Total Interactions: {report['system_maturity']['total_interactions']}")
    if report['system_maturity']['total_interactions'] == 2: # 1 root + 1 child
        print("PASS: Evolution metrics connected")
    else:
        print(f"FAIL: Expected 2 interactions, got {report['system_maturity']['total_interactions']}")

if __name__ == "__main__":
    asyncio.run(test_observability_flow())
