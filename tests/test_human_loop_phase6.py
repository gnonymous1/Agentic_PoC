import asyncio
import json
from core.coordinator import CoordinatorAgent
from core.human_loop import InteractionStatus

async def test_human_synergy():
    config = {
        "providers": {
            "openai": {"api_key": "test"}
        }
    }
    coordinator = CoordinatorAgent(config)

    # Mock LLM for Clarification check
    call_count = 0
    async def mock_llm_complete(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        prompt = messages[0]["content"]
        
        # If it looks like a clarification-refined prompt, return high confidence
        if "Clarification:" in prompt:
            return {"content": json.dumps({
                "intent": "delete file with specific name",
                "complexity": "simple",
                "approach": "direct",
                "confidence": 0.9
            })}
        
        # Default: Low confidence trigger
        return {"content": json.dumps({
            "intent": "idk maybe delete something",
            "complexity": "simple",
            "approach": "direct",
            "confidence": 0.3
        })}

    coordinator.llm.complete = mock_llm_complete
    
    # Let's mock _decompose to avoid failure
    async def mock_decompose(user_input, reasoning):
        return {"execution_groups": []}
    coordinator._decompose = mock_decompose

    print("--- Testing Clarification Gate ---")
    
    # Start process in background
    process_task = asyncio.create_task(coordinator.process("delete that thing"))
    
    # Retry loop for pending tasks
    pending = []
    for _ in range(20):
        await asyncio.sleep(0.1)
        pending = coordinator.human_loop.get_pending_tasks()
        if any(t["type"] == "clarification" for t in pending):
            break
            
    print(f"Pending tasks (Clarification): {[t['type'] for t in pending]}")
    
    if pending and pending[0]["type"] == "clarification":
        print("PASS: Clarification requested")
        coordinator.human_loop.submit_response(pending[0]["id"], "I meant delete index.tmp")
    else:
        print("FAIL: Clarification gate not triggered")
    
    try:
        await asyncio.wait_for(process_task, timeout=2)
    except Exception as e:
        print(f"Process ended: {type(e).__name__}")
    
    if call_count >= 2:
        print("PASS: Re-reasoned after clarification")

    print("\n--- Testing Approval Gate ---")
    # Mock for approval
    async def mock_llm_approval_flow(user_input, context=None):
        return {
            "intent": "delete file",
            "complexity": "simple",
            "approach": "direct",
            "confidence": 1.0
        }
    
    async def mock_decompose_sensitive(user_input, reasoning):
        return {
            "execution_groups": [
                {
                    "group_id": 1,
                    "tasks": [{"task_id": "t1", "agent": "arch", "action": "delete_file"}]
                }
            ]
        }
    
    coordinator._reason = mock_llm_approval_flow
    coordinator._decompose = mock_decompose_sensitive
    
    # Mock execution to check _is_sensitive
    process_task_2 = asyncio.create_task(coordinator.process("delete file"))
    
    # Retry loop for pending tasks
    pending = []
    for _ in range(20):
        await asyncio.sleep(0.1)
        pending = coordinator.human_loop.get_pending_tasks()
        if any(t["type"] == "approval" for t in pending):
            break
            
    print(f"Pending tasks (Approval Gate): {[t['type'] for t in pending]}")
    
    if pending and pending[0]["type"] == "approval":
        print("PASS: Approval requested for sensitive task")
        coordinator.human_loop.submit_response(pending[0]["id"], True)
    else:
        print("FAIL: Approval gate not triggered")
    
    # Clean up
    process_task_2.cancel()
    try: await process_task_2
    except asyncio.CancelledError: pass

if __name__ == "__main__":
    asyncio.run(test_human_synergy())
