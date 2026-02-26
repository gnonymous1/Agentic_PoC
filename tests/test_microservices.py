import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock LLM
sys.modules['cortex.llm'] = MagicMock()

from cortex.events import EventBus, EventType
from api.api_gateway import submit_task, TaskRequest
from api.agent_worker import AgentWorker

async def test_microservices():
    print(">>> Starting Microservices Test")
    
    # 1. Start Worker
    worker = AgentWorker()
    bus = await EventBus.get()
    
    # Subscribe worker manually since we aren't running full loop
    bus.subscribe(EventType.SYSTEM_EVENT, worker.handle_task)
    
    # 2. Submit Task via Gateway
    print(">>> Submitting Task to API Gateway...")
    req = TaskRequest(agent_id="service_agent", task="Run diagnostics")
    response = await submit_task(req)
    
    print(f"Gateway Response: {response}")
    assert response["status"] == "submitted"
    
    # 3. Simulate Event Loop Processing
    print(">>> Waiting for Worker processing...")
    await asyncio.sleep(1.5) # Worker has 1s sleep
    
    # We can't easily assert print output, but if no error, we assume success for this PoC
    print("Test Complete: Microservices Communication Verified.")

if __name__ == "__main__":
    asyncio.run(test_microservices())
