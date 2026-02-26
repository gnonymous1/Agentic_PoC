import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.evolution.learning import learning_engine
from agent_fabric.agent import BaseAgent

# Mock LLM
sys.modules['cortex.llm'] = MagicMock()
sys.modules['cortex.llm'].get_llm = MagicMock(return_value=MagicMock())

async def test_rl_feedback():
    print(">>> Starting RL Feedback Loop Test")
    
    # 1. Create Agent
    agent = BaseAgent(name="LearningAgent", system_prompt="You learn.", role="tester")
    tool_name = "test_tool"
    
    # Reset score manually for test reproducibility
    learning_engine.weights[f"{agent.role}:{tool_name}"] = 0.0
    
    # 2. Check Initial Score
    initial_score = learning_engine.get_tool_score(agent.role, tool_name)
    print(f"Initial Score for {tool_name}: {initial_score}")
    assert initial_score == 0.0
    
    # 3. Simulate Successful Usage
    print(">>> Providing SUCCESS feedback...")
    agent.provide_feedback(tool_name, "success")
    
    new_score = learning_engine.get_tool_score(agent.role, tool_name)
    print(f"Score after success: {new_score}")
    assert new_score > initial_score
    assert new_score > 0.0
    
    # 4. Simulate Failure Usage
    print(">>> Providing FAILURE feedback...")
    agent.provide_feedback(tool_name, "failure")
    
    final_score = learning_engine.get_tool_score(agent.role, tool_name)
    print(f"Score after failure: {final_score}")
    assert final_score < new_score
    
    print("Test Complete: Learning Loop Verified.")

if __name__ == "__main__":
    asyncio.run(test_rl_feedback())
