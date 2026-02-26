import asyncio
import sys
import os

# Adjust path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.events import EventBus, EventType, Event
from agent_fabric.agent import BaseAgent

class AgentWorker:
    def __init__(self):
        self.bus = None
        self.running = False
        self.agents = {} # Cache instantiated agents

    async def start(self):
        self.bus = await EventBus.get()
        self.bus.subscribe(EventType.SYSTEM_EVENT, self.handle_task)
        self.running = True
        print("[Worker] Agent Worker started. Listening for tasks...")
        
        while self.running:
            await asyncio.sleep(1)

    async def handle_task(self, event: Event):
        data = event.data
        if data.get("action") == "task_submitted":
            agent_id = data.get("agent_id")
            task = data.get("task")
            print(f"[Worker] Processing task for {agent_id}: {task}")
            
            # Simulate processing (In real logic, we'd load the agent efficiently)
            # For POC, we just acknowledge
            await asyncio.sleep(1)
            print(f"[Worker] Task completed for {agent_id}")
            
            # Emit completion (optional)
            
if __name__ == "__main__":
    worker = AgentWorker()
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        print("[Worker] Stopping...")
