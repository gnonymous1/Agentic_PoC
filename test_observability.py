import asyncio
import json
import traceback
from core.coordinator import CoordinatorAgent
from config.settings import load_config

async def main():
    print("[TEST] Starting Observability Test...")
    
    try:
        config_obj = load_config()
        config = config_obj.model_dump()
    except Exception as e:
        print(f"[WARN] Failed to load config: {e}")
        config = {"providers": {"openai": {"api_key": "dummy"}, "ollama": {}}}

    # Initialize Coordinator
    coordinator = CoordinatorAgent(config)
    print("[OK] Coordinator Initialized")

    # Send a dummy request
    user_input = "What is the capital of France?"
    print(f"\n[SEND] Sending request: '{user_input}'")
    
    try:
        response = await coordinator.process(user_input, source="test_script")
        print("\n[RECV] Response received:", json.dumps(response, indent=2))
    except Exception as e:
        print(f"\n[ERR] Error processing request: {e}")
        # traceback.print_exc()

    # Inspect Observability Data
    print("\n--- OBSERVABILITY REPORT ---")
    
    obs = coordinator.observability
    
    # 1. Traces
    print(f"\n- Traces: {len(obs.traces)}")
    for span_id, span in obs.traces.items():
        duration = (span.end_time - span.start_time) * 1000 if span.end_time else 0
        print(f"  - [{span.status.upper()}] {span.operation:<20} ({duration:.2f}ms) | Agent: {span.agent}")
        if span.metadata:
            print(f"    Tags: {span.metadata}")

    # 2. Metrics
    metrics = obs.get_metrics_summary()
    print(f"\n- Metrics Summary:")
    print(json.dumps(metrics, indent=2))

    # 3. Costs
    costs = obs.cost_tracker.get_cost_report()
    print(f"\n- Cost Report:")
    print(json.dumps(costs, indent=2))

    # 4. Performance
    print(f"\n- Performance Score: {obs.performance_tracker.get_performance_score()}")

if __name__ == "__main__":
    asyncio.run(main())
