import asyncio
import os
import json
from core.learning import AdaptiveLearningEngine
from core.memory import VectorMemory

async def test_adaptive_learning():
    config = {
        "memory": {"vector_store_path": "./data/test_memory.json"}
    }
    
    # Ensure clean state
    if os.path.exists("./data/test_memory.json"):
        import shutil
        shutil.rmtree(os.path.dirname("./data/test_memory.json"), ignore_errors=True)

    memory = VectorMemory(config)
    learning = AdaptiveLearningEngine(config, memory)

    print("--- Testing Learning Extraction ---")
    user_input = "Write a report about the stock market."
    response = "The stock market is up today..."
    feedback = {"comment": "I prefer extremely concise bullet points and a professional tone.", "rating": 5}
    
    await learning.learn_from_interaction(user_input, response, feedback, task_type="reasoning")
    print("Logged interaction with feedback.")

    # Wait a bit for async operations if any (though currently synchronous file writes)
    await asyncio.sleep(0.5)

    print("\n--- Testing Prompt Refinement ---")
    base_prompt = "Generate a summary of the quarterly earnings."
    task_type = "reasoning"
    
    refined_prompt = await learning.get_refined_prompt(base_prompt, task_type)
    print(f"Refined Prompt:\n{refined_prompt}")
    
    if "extremely concise bullet points" in refined_prompt and "professional tone" in refined_prompt:
        print("\nPASS: Preferences correctly extracted and applied to prompt.")
    else:
        print("\nFAIL: Preferences missing from refined prompt.")
        
    # Test task type specific search
    print("\n--- Testing Decomposition Refinement ---")
    base_decomp = "Plan the execution for building a website."
    refined_decomp = await learning.get_refined_prompt(base_decomp, "decomposition")
    if "extremely concise" in refined_decomp:
         print("PASS: Preferences applied to decomposition as well.")
    else:
         print("FAIL: Preferences not found in decomposition prompt.")

if __name__ == "__main__":
    asyncio.run(test_adaptive_learning())
