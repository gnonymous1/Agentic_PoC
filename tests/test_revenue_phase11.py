import asyncio
from core.coordinator import CoordinatorAgent
from billing.tiers import ServiceTier

async def test_revenue_scale():
    config = {"providers": {"openai": {"api_key": "test"}}}
    coordinator = CoordinatorAgent(config)

    print("--- Testing Quota Enforcement ---")
    user_id = "free_user_1"
    coordinator.quota_manager.set_user_tier(user_id, ServiceTier.FREE)
    
    # Mocking execution parts to avoid real LLM calls for quota testing
    async def mock_reason(ui, ctx=None): return {"intent": "test"}
    async def mock_decompose(ui, r): return {"execution_groups": []}
    coordinator._reason = mock_reason
    coordinator._decompose = mock_decompose

    # Simulate hitting parallel task limit
    coordinator.quota_manager.record_usage(user_id, "task_start")
    coordinator.quota_manager.record_usage(user_id, "task_start")
    
    print(f"Stats before check: {coordinator.quota_manager.get_user_stats(user_id)}")
    
    res = await coordinator.process("test request", user_id=user_id)
    print(f"Process Result: {res}")
    
    if "quota exceeded" in res.lower():
        print("PASS: Parallel task quota enforced")
    else:
        print("FAIL: Quota not enforced")

    print("\n--- Testing Tier Upgrades ---")
    coordinator.quota_manager.set_user_tier(user_id, ServiceTier.PRO)
    res_pro = await coordinator.process("test request", user_id=user_id)
    print(f"Pro Result: {res_pro}")
    
    if "quota exceeded" not in res_pro.lower():
        print("PASS: Upgrade correctly increased limits")
    else:
        print("FAIL: Upgrade did not increase limits")

if __name__ == "__main__":
    asyncio.run(test_revenue_scale())
