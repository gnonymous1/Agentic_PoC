import os
import uvicorn
import secrets
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, Optional
from core.coordinator import CoordinatorAgent
from agents.dynamic_tool_agent import DynamicToolAgent

app = FastAPI(title="OMNIOS API", description="Secure Agentic Interface")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
API_KEY_HEADER = APIKeyHeader(name="X-API-Key")

def get_valid_api_keys():
    key = os.getenv("OMNIOS_API_KEY")
    if not key:
        key = secrets.token_urlsafe(32)
        print(f"WARNING: OMNIOS_API_KEY not set. Generated temporary secure key: {key}")
    return {key}

VALID_API_KEYS = get_valid_api_keys()

async def get_api_key(api_key: str = Security(API_KEY_HEADER)):
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# State
coordinator: Optional[CoordinatorAgent] = None

class RequestModel(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = {}

@app.on_event("startup")
async def startup_event():
    global coordinator
    config = {
        "providers": {
            "openai": {"api_key": os.getenv("OPENAI_API_KEY", "test")}
        }
    }
    coordinator = CoordinatorAgent(config)
    
    # Register default agents for the platform view
    dt_agent = DynamicToolAgent(config, "DynamicToolAgent")
    coordinator.register_agent(dt_agent)

@app.post("/process")
async def process_request(req: RequestModel, api_key: str = Depends(get_api_key)):
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    
    # Check for custom provider keys in context to allow UI-driven experimentation
    custom_key = req.context.get("openai_api_key")
    if custom_key:
        coordinator.llm.config["providers"]["openai"]["api_key"] = custom_key

    try:
        response = await coordinator.process(
            req.query, 
            context=req.context,
            user_id=req.context.get("user_id", "default_user")
        )
        return {"status": "success", "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class WorkflowModel(BaseModel):
    name: str

@app.post("/workflows/execute")
async def execute_workflow(req: WorkflowModel, api_key: str = Depends(get_api_key)):
    if not coordinator:
        raise HTTPException(status_code=503, detail="Coordinator not initialized")
    
    # Map friendly names to actual system tasks
    if "Security Audit" in req.name:
        task = "Perform a full security audit of the current project and generate a report summary."
    elif "Performance" in req.name:
        task = "Analyze the system performance and latency metrics, looking for bottlenecks."
    else:
        task = f"Execute system workflow: {req.name}"

    try:
        # Run the task through the coordinator
        response = await coordinator.process(task, source="workflow_engine")
        return {"status": "success", "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
async def list_agents(api_key: str = Depends(get_api_key)):
    if not coordinator:
        return {"agents": []}
    
    agents_list = []
    for name, agent in coordinator.agents.items():
        agents_list.append({
            "name": name,
            "capabilities": agent.get_capabilities(),
            "status": "active"
        })
    return {"agents": agents_list}

@app.get("/skills")
async def list_skills(api_key: str = Depends(get_api_key)):
    from agent_fabric.tool_loader import load_dynamic_tools
    tools = load_dynamic_tools()
    return {
        "skills": [
            {"name": t.name, "description": t.description} for t in tools
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "online", "version": "0.4.0-phase7"}

# Serve Web Frontend (Catch-all after specific routes)
app.mount("/", StaticFiles(directory="web", html=True), name="web")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
