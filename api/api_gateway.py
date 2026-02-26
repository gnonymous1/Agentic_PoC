import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from typing import Dict, Any

# Local imports
# Adjust path if needed
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cortex.events import EventBus, EventType

app = FastAPI(title="AgentOS API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskRequest(BaseModel):
    agent_id: str
    task: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "api_gateway"}

@app.post("/tasks")
async def submit_task(req: TaskRequest):
    """
    Submit a task to the Agent Worker via EventBus
    """
    bus = await EventBus.get()
    
    # Emit task event
    await bus.emit_async(
        EventType.SYSTEM_EVENT,
        {
            "action": "task_submitted",
            "agent_id": req.agent_id,
            "task": req.task
        },
        source="api_gateway"
    )
    
    return {"status": "submitted", "task": req.task}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
