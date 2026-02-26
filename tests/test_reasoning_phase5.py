import asyncio
from core.reasoning_engine import AdvancedReasoningEngine
from core.llm_router import LLMRouter

async def test_advanced_reasoning():
    config = {
        "providers": {
            "openai": {"api_key": "test"}
        }
    }
    router = LLMRouter(config)
    engine = AdvancedReasoningEngine(router)

    # Mock responses
    call_history = []
    async def mock_call(messages, **kwargs):
        prompt = messages[0]["content"]
        call_history.append(prompt)
        if "Refine" in prompt:
            return {"content": "Final Refined Answer with X and Y."}
        elif "Critique" in prompt:
            return {"content": "The initial thought missed X and Y."}
        elif "different approaches" in prompt:
            return {"content": "Approach 1: Go left --- Approach 2: Go right"}
        elif "Evaluate" in prompt:
            return {"content": "Approach 2 is better. Solution: Right."}
        else:
            return {"content": "Initial Thought."}

    router.complete = mock_call

    print("--- Testing Reflection Loop ---")
    res = await engine.reason_with_reflection("Solve for X.", iterations=1)
    print(f"Result: {res}")
    if "Refined" in res and len(call_history) >= 3:
        print("PASS: Reflection cycle completed (Thought -> Critique -> Refine)")
    else:
        print("FAIL: Reflection cycle incomplete")

    print("\n--- Testing Tree of Thoughts ---")
    call_history.clear()
    res = await engine.reason_tree_of_thoughts("Which way to go?", num_thoughts=2)
    print(f"Result: {res}")
    if "Solution: Right" in res and len(call_history) >= 2:
        print("PASS: Tree of Thoughts completed (Gen -> Eval)")
    else:
        print("FAIL: ToT incomplete")

if __name__ == "__main__":
    asyncio.run(test_advanced_reasoning())
