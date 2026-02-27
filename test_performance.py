import asyncio
import time
from core.llm_router import LLMRouter, Provider
from core.caching import CacheManager
from core.coordinator import CoordinatorAgent
from core.monitoring import ObservabilityEngine

# Mock config
MOCK_CONFIG = {
    "providers": {
        "openai": {"api_key": "dummy"},
        "ollama": {"base_url": "http://localhost:11434"}
    },
    "memory": {"vector_store_path": "./data/test_memory.json"} 
}

async def mock_provider_call(*args, **kwargs):
    await asyncio.sleep(1.0) # Simulate 1s latency
    return {
        "content": "Mock Response",
        "usage": {"prompt_tokens": 10, "completion_tokens": 10}
    }

async def test_caching():
    print("\n[TEST] Testing Caching Layer...")
    router = LLMRouter(MOCK_CONFIG)
    router._call_openai_compatible = mock_provider_call # Bypass retry logic for simple mocking
    
    # 1. First Call (Miss)
    print("  Request 1 (Cold)...")
    start = time.time()
    await router.complete([{"role": "user", "content": "Hello"}], task_type="general")
    duration1 = time.time() - start
    print(f"  Duration: {duration1:.2f}s")
    
    # 2. Second Call (Hit)
    print("  Request 2 (Warm)...")
    start = time.time()
    res = await router.complete([{"role": "user", "content": "Hello"}], task_type="general")
    duration2 = time.time() - start
    print(f"  Duration: {duration2:.2f}s")
    
    if duration2 < 0.1:
        print("  [PASS] Cache Hit (Fast)")
    else:
        print("  [FAIL] Cache Miss (Slow)")

async def test_parallel_execution():
    print("\n[TEST] Testing Parallel Execution...")
    
    # Setup Coordinator with mock agents
    obs = ObservabilityEngine(MOCK_CONFIG)
    coordinator = CoordinatorAgent(MOCK_CONFIG)
    coordinator.observability = obs
    
    # Mock Agent that sleeps
    class MockAgent:
        def __init__(self, name): self.name = name
        async def execute(self, action, params):
            print(f"    {self.name} starting {action}...")
            await asyncio.sleep(1.0)
            print(f"    {self.name} finished {action}.")
            return "done"

    coordinator.agents["agent_a"] = MockAgent("agent_a")
    coordinator.agents["agent_b"] = MockAgent("agent_b")
    
    # Create a plan with 2 parallel tasks
    plan = {
        "execution_groups": [
            {
                "group_id": "group1",
                "tasks": [
                    {"task_id": "t1", "agent": "agent_a", "action": "work", "params": {}},
                    {"task_id": "t2", "agent": "agent_b", "action": "work", "params": {}},
                ]
            }
        ]
    }
    
    print("  Executing plan with 2 parallel tasks (1s each)...")
    start = time.time()
    await coordinator._execute_plan("root_task", plan)
    duration = time.time() - start
    print(f"  Total Duration: {duration:.2f}s")
    
    if duration < 1.5:
        print("  [PASS] Executed in parallel (< 2s)")
    else:
        print("  [FAIL] Executed sequentially (> 1.5s)")

async def main():
    await test_caching()
    await test_parallel_execution()

if __name__ == "__main__":
    asyncio.run(main())
