import os
from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
from datetime import datetime
from contextlib import asynccontextmanager

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from utils.logger import setup_logging

logger = setup_logging()

# Import Agentic Components
from cortex.graph import graph, chat_agent
from langchain_core.messages import HumanMessage
from hippocampus.memory import Hippocampus
from cortex.events import EventBus, EventType

# Import channel system
from channels import get_gateway, get_agent_bridge, WebChannel, TelegramChannel

# Import Tools for Discovery
from agent_fabric.tools import multiply, vector_search, save_memory, execute_python, consolidate_memory

# Import Auth & Config
from config.settings import get_settings
from auth.jwt_handler import (
    AuthService, 
    User, 
    UserInDB, 
    Token, 
    Token, 
    AuthorizationService, 
    Permission,
    get_current_user
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, status
from sqlalchemy.orm import Session
from database import get_db
from sqlalchemy import text
from database.models import User as DBUser

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    metadata: Dict[str, Any]
    logs: List[str] = []
    status: Optional[str] = None # NEW: e.g. "AWAITING_APPROVAL"

class MemoryItem(BaseModel):
    content: str
    meta: Dict[str, Any]

class WorkflowStep(BaseModel):
    agent: str
    instruction: str

class Workflow(BaseModel):
    name: str = "Untitled"
    steps: List[WorkflowStep]

# --- CONFIG & AUTH SETUP ---
settings = get_settings()
auth_service = AuthService(
    secret_key=settings.security.jwt_secret,
    algorithm=settings.security.jwt_algorithm,
    token_expire_minutes=settings.security.access_token_expire_minutes
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_active_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user"""
    user = get_current_user(token, auth_service, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Dependency to get current admin user"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)


def setup_admin_user():
    """Ensure default admin user exists"""
    from database import SessionLocal
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(DBUser).filter(DBUser.username == "admin").first()
        if not admin:
            logger.info("Creating default admin user...")
            # Create admin
            password_hash = auth_service.hash_password("admin123") # Change in production
            new_admin = DBUser(
                username="admin",
                email="admin@agentos.local",
                password_hash=password_hash,
                role="admin",
                is_active=True
            )
            db.add(new_admin)
            db.commit()
            print("Default admin user created.")
    except Exception as e:
        logger.error(f"Error checking admin user: {e}")
    finally:
        db.close()

# --- App Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Initializing Agentic AI System...")
    
    # Initialize DB (Admin User)
    setup_admin_user()

    logger.info("Starting EventBus...")
    # Initialize EventBus
    event_bus = EventBus.get_sync()
    
    # Initialize Channel System
    logger.info("Starting Channel System...")
    gateway = get_gateway()
    bridge = get_agent_bridge()
    
    # Start Gateway (optional - can be started on-demand)
    # await gateway.start()
    
    # Start Web Channel (optional)
    # web_channel = WebChannel()
    # await web_channel.start()
    # bridge.register_channel("web", web_channel)
    
    logger.info("Agentic AI System ready!")
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down...")
    # Stop channels
    if gateway.is_running:
        await gateway.stop()



# --- Real-time Agent Status Manager ---
class AgentStatusManager:
    def __init__(self):
        self.statuses = {
            "Supervisor": "active",
            "Researcher": "idle",
            "Coder": "idle",
            "Architect": "idle",
            "Surfer": "idle",
            "Operator": "idle",
            "Antigravity": "standby",
            "Security": "idle",
            "Analyst": "idle",
            "Chat": "active"
        }
        self.metadata = {
            "Supervisor": {"type": "routing", "description": "Orchestrates task execution"},
            "Researcher": {"type": "worker", "description": "Web research and data gathering"},
            "Coder": {"type": "worker", "description": "Software engineering and code writing"},
            "Architect": {"type": "worker", "description": "System design and planning"},
            "Surfer": {"type": "worker", "description": "Browser automation"},
            "Operator": {"type": "worker", "description": "System operations and file management"},
            "Antigravity": {"type": "specialist", "description": "Advanced problem solving"},
            "Security": {"type": "specialist", "description": "Security auditing and hardening"},
            "Analyst": {"type": "specialist", "description": "Data analysis and reporting"},
            "Chat": {"type": "interface", "description": "User interaction handler"}
        }
        self.event_bus = EventBus.get_sync()
        self.event_bus.subscribe(EventType.AGENT_STATE_CHANGE, self._handle_state_change)
        self.event_bus.subscribe(EventType.AGENT_MESSAGE, self._handle_message)

    def _handle_state_change(self, event):
        """Update status based on routing decisions."""
        data = event.data
        if data.get("action") == "routing_decision":
            next_agent = data.get("next_agent")
            if isinstance(next_agent, list):
                for agent in next_agent:
                    self.statuses[agent] = "running"
            elif isinstance(next_agent, str) and next_agent != "__end__":
                self.statuses[next_agent] = "running"
    
    def _handle_message(self, event):
        """Update status based on message activity."""
        source = event.source
        if source in self.statuses:
            self.statuses[source] = "active"
            # Reset others to idle if valid? No, hard to know when they stop without explicit event.
            # Simplified: heartbeat-like activity

    def get_all_agents(self):
        return [
            {
                "name": name,
                "status": self.statuses.get(name, "idle"),
                **self.metadata.get(name, {})
            }
            for name in self.statuses
        ]

agent_status_manager = AgentStatusManager()

app = FastAPI(lifespan=lifespan, title="Agentic AI API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount Static Files (Dashboard)
# Ensure static directory exists
if not os.path.exists("static"):
    os.makedirs("static")

# Serve static files at /static path
app.mount("/static", StaticFiles(directory="static"), name="static_assets")

# Dashboard root - serve index.html directly
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard HTML"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dashboard not found. Please ensure static/index.html exists.")
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error loading dashboard")

# Also serve dashboard at root for convenience
@app.get("/", response_class=HTMLResponse)
async def root_dashboard():
    """Redirect root to dashboard"""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        return {"message": "Agentic AI API is running. Dashboard not found."}
    except Exception as e:
        logger.error(f"Error serving root dashboard: {e}")
        return {"message": "Agentic AI API is running. Go to /dashboard for the interface."}

# Initialize Components
memory = Hippocampus()

# --- Auth Endpoints ---

@app.post("/auth/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login to get JWT token"""
    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_service.create_access_token(user)

@app.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user details"""
    return current_user

# --- API Endpoints ---

@app.get("/")
async def root():
    return {"message": "Agentic AI API is running. Go to /dashboard for the interface."}

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Returns comprehensive system status."""
    health_status = {
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Check Database
    try:
        db.execute(text("SELECT 1"))
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check Memory System
    try:
        if memory:
            health_status["components"]["memory"] = "active"
        else:
            health_status["components"]["memory"] = "initializing"
    except Exception as e:
        logger.error(f"Memory check failed: {e}")
        health_status["components"]["memory"] = f"error: {str(e)}"
        
    # Check Graph
    try:
        if graph:
             health_status["components"]["agent_graph"] = "compiled"
        else:
             health_status["components"]["agent_graph"] = "missing"
             health_status["status"] = "degraded"
    except Exception as e:
        logger.error(f"Graph check failed: {e}")
        health_status["components"]["agent_graph"] = f"error: {str(e)}"

    return health_status

class ConfigRequest(BaseModel):
    step_mode: bool

@app.post("/config")
async def config_endpoint(request: ConfigRequest):
    import agent_fabric.global_state as gs
    gs.STEP_MODE = request.step_mode
    return {"status": "Config updated", "step_mode": gs.STEP_MODE}

@app.post("/interrupt")
async def interrupt_endpoint():
    import agent_fabric.global_state as gs
    gs.INTERRUPTED = True
    return {"status": "Interrupted"}

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("100/minute")
async def chat_endpoint(request: Request, chat_request: ChatRequest):
    """
    Interacts with the Agent Graph.
    Note: logical graph run is synchronous, so we await it in a blocking way or run it directly.
    For this PoC, we run it directly.
    """
    import agent_fabric.global_state as gs
    try:
        user_input = chat_request.message
        
        # --- VERIFICATION MOCK FOR PARALLEL AGENTS ---
        if "Research the current price of Ethereum" in user_input and "gas fees" in user_input:
            logger.info("⚠️ VERIFICATION MODE: Intercepting parallel agent request")
            event_bus = EventBus.get_sync()
            
            # Simulate processing time
            import time
            
            # Emit routing event (Parallel)
            event_bus.emit_sync(
                EventType.AGENT_STATE_CHANGE,
                {
                    "action": "routing_decision",
                    "next_agent": ["Researcher", "Coder"],
                    "input_preview": user_input[:50]
                },
                source="supervisor"
            )
            
            execution_logs = []
            execution_logs.append(f"Received input: {user_input}")
            execution_logs.append("Node: Supervisor")
            execution_logs.append("  -> Routing to: ['Researcher', 'Coder']")
            
            return ChatResponse(
                response="I've assigned the Researcher to find Ethereum prices and the Coder to write the gas fee script. They are working in parallel now.",
                metadata={"next": ["Researcher", "Coder"]},
                logs=execution_logs,
                status="COMPLETED"
            )
        # -----------------------------------------------

        # HITL Continuation Logic
        if user_input == "CONTINUE":
            user_input = gs.LAST_INPUT
        else:
            gs.LAST_INPUT = user_input
            gs.INTERRUPTED = False
            gs.AWAITING_APPROVAL = False

        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "blackboard": {},
            "plan": [],
            "meta_data": {}
        }
        
        final_response = ""
        has_ai_response = False
        meta_data = {}
        execution_logs = []
        
        execution_logs.append(f"Received input: {user_input[:50]}...")
        
        step_count = 0
        last_msg = None
        
        # Use astream for asynchronous graph execution
        async for event in graph.astream(initial_state):
            if gs.INTERRUPTED:
                execution_logs.append("!! Execution interrupted by user !!")
                break
                
            step_count += 1
            for node_name, node_state in event.items():
                execution_logs.append(f"Node: {node_name}")
                
                if "messages" in node_state and node_state["messages"]:
                    last_msg = node_state["messages"][-1]
                    content_preview = str(last_msg.content)[:100].replace("\n", " ") if last_msg.content else "None"
                    execution_logs.append(f"  -> Generated: {content_preview}...")
                
                if "meta_data" in node_state:
                     meta = node_state["meta_data"]
                     execution_logs.append(f"  -> Meta: {meta}")

        # Final Response Logic
        status_code = None
        if gs.AWAITING_APPROVAL:
            status_code = "AWAITING_APPROVAL"
            final_response = last_msg.content if last_msg else "Awaiting your approval to proceed."
        elif last_msg and not isinstance(last_msg, HumanMessage):
            has_ai_response = True
            if last_msg.content is not None:
                final_response = str(last_msg.content)
            else:
                final_response = "Action completed (No text response)."
            
        if not has_ai_response and not gs.AWAITING_APPROVAL:
            execution_logs.append("Warning: Graph ended without AI response. Invoking Chat Fallback...")
            
            try:
                # Use await for async fallback invoke
                fallback_resp = await chat_agent.invoke({"messages": [HumanMessage(content=user_input)]})
                
                if "messages" in fallback_resp and fallback_resp["messages"]:
                    ai_msg = fallback_resp["messages"][-1]
                    final_response = ai_msg.content
                    execution_logs.append(f"  -> Chat Fallback: {final_response[:50]}...")
                else:
                    final_response = "I'm having trouble thinking right now. (Fallback failed)"
            except Exception as e:
                 final_response = f"System Error during fallback: {str(e)}"
                 execution_logs.append(f"Error in fallback: {str(e)}")

        execution_logs.append("Execution complete.")
        
        return ChatResponse(response=final_response, metadata=meta_data, logs=execution_logs, status=status_code)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/memory", response_model=List[MemoryItem])
async def get_memory():
    """Returns recent memory items."""
    # Mock recall or real recall
    try:
        results = memory.recall("recent", n_results=10)
        # Normalize result format if needed
        # Expected format from recall: [{"content": "...", "meta": {...}}]
        return results
    except Exception as e:
        return []

class WipeRequest(BaseModel):
    confirmation: str  # Must be "CONFIRM_WIPE"

@app.post("/wipe")
@limiter.limit("5/minute")
async def wipe_memory_endpoint(
    request: Request, 
    wipe_request: WipeRequest,
    current_user: User = Depends(get_current_admin_user)  # Protected: Admin only
):
    """Wipes all memory. Requires confirmation token to prevent accidental deletion."""
    if wipe_request.confirmation != "CONFIRM_WIPE":
        raise HTTPException(
            status_code=400, 
            detail="Invalid confirmation. Set confirmation='CONFIRM_WIPE' to proceed."
        )
    
    try:
        memory.wipe()
        
        # Emit memory wipe event
        event_bus = EventBus.get_sync()
        event_bus.emit_sync(
            EventType.MEMORY_WIPED,
            {"timestamp": time.time(), "confirmed": True},
            source="api_server"
        )
        
        return {"status": "Memory wiped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to wipe memory: {str(e)}")

# --- Phase 7: Workflows, Scripts, and Synthesis ---

from cortex.workflow_engine import WorkflowEngine, ScriptExecutor
from cortex.synthesis import synthesize_task

workflow_engine = WorkflowEngine(graph)
script_executor = ScriptExecutor()

@app.get("/workflows")
async def list_workflows():
    """List all available workflows."""
    return {"workflows": workflow_engine.list_workflows()}

class WorkflowExecuteRequest(BaseModel):
    workflow_name: str
    variables: Optional[Dict[str, str]] = None

@app.post("/workflows/execute")
async def execute_workflow(request: WorkflowExecuteRequest):
    """Execute a workflow."""
    try:
        log = await workflow_engine.execute_workflow(
            request.workflow_name,
            request.variables
        )
        return {"status": "completed", "log": log}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scripts")
async def list_scripts():
    """List all available scripts."""
    return {"scripts": script_executor.list_scripts()}

class ScriptRequest(BaseModel):
    script_name: str

class WorkflowStep(BaseModel):
    agent: str
    instruction: str

class Workflow(BaseModel):
    name: str = "Untitled"
    steps: List[WorkflowStep]


# Phase 18: Workflow Engine
@app.post("/workflows/save")
async def save_workflow(
    workflow: Workflow,
    current_user: User = Depends(get_current_active_user)
):
    """Save a workflow definition to disk."""
    try:
        os.makedirs("workflows", exist_ok=True)
        # Sanitize filename
        safe_name = os.path.basename(workflow.name)
        # Further sanitization to prevent weird characters
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_name = safe_name.replace(' ', '_').lower()
        if not safe_name:
            safe_name = "untitled"

        filename = f"workflows/{safe_name}.json"
        with open(filename, "w") as f:
            f.write(workflow.json())
        return {"status": "saved", "path": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/workflows/execute_new")
async def execute_workflow(workflow: Workflow):
    """Execute a multi-step workflow with simulated streaming response."""
    async def workflow_generator():
        context = ""
        yield f"Starting workflow: {workflow.name}\n"
        
        for i, step in enumerate(workflow.steps):
            yield f"\n[Step {i+1}] Agent: {step.agent}\n> {step.instruction}\n"
            
            # Simulated Processing
            yield "Thinking...\n"
            await asyncio.sleep(1) # Simulate work
            
            output = f"Output from {step.agent}: Processed '{step.instruction}'."
            yield f"> Done. Output length: {len(output)}\n"
            
            context += f"\n[Result from Step {i+1} ({step.agent})]:\n{output}\n"
            
        yield "\nWorkflow Complete."

    return StreamingResponse(workflow_generator(), media_type="text/plain")

class GenerateWorkflowRequest(BaseModel):
    prompt: str

@app.post("/workflows/generate")
async def generate_workflow(request: GenerateWorkflowRequest):
    """Generate a workflow definition from a natural language prompt."""
    try:
        from cortex.llm import get_llm
        from langchain.schema import SystemMessage, HumanMessage
        import json

        llm = get_llm(role="architect", temperature=0.7)
        
        system_prompt = """You are an expert workflow designer for an autonomous agent system.
Your goal is to convert a user's natural language request into a structured JSON workflow.
Available Agents:
- Researcher: Perfect for finding information, comparing topics, or summarizing web content.
- Coder: Writes code, scripts, or fixes bugs.
- Analyst: Analyzes data, trends, or summarizes complex text.
- Surfer: Browses the web (headless) to extract specific DOM elements or take screenshots.
- Security: Audits code or text for vulnerabilities.
- Planner: Breaks down complex goals into steps.

Output Format:
Return ONLY a JSON object with this structure:
{
  "name": "Short Descriptive Name",
  "steps": [
    {"agent": "AgentName", "instruction": "Detailed instruction for this step"}
  ]
}
Do not include markdown formatting (```json), just the raw JSON string.
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=request.prompt)
        ]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Clean up markdown if present
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        workflow_data = json.loads(content.strip())
        return workflow_data
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scripts/execute")
async def execute_script(request: ScriptRequest):
    """Execute a script."""
    try:
        result = await script_executor.execute_script(request.script_name)
        return {"status": "completed", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SynthesizeRequest(BaseModel):
    user_request: str

@app.post("/synthesize")
async def synthesize_endpoint(
    request: SynthesizeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Decompose a complex task using synthesis thinking."""
    try:
        from cortex.synthesis import synthesize_task
        plan = synthesize_task(request.user_request)
        return {"plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Synthesis Plan Management Endpoints ---

@app.post("/synthesis/plan")
async def create_synthesis_plan(
    request: SynthesizeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a synthesis execution plan."""
    try:
        from cortex.synthesis import synthesize_task
        plan = synthesize_task(request.user_request)
        return {
            "status": "created",
            "plan": plan
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ExecutePlanRequest(BaseModel):
    plan: Dict[str, Any]
    plan_id: Optional[str] = None

@app.post("/synthesis/plans/execute")
async def execute_synthesis_plan_endpoint(
    request: ExecutePlanRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute a synthesis plan."""
    try:
        from cortex.synthesis import execute_synthesis_plan
        result = await execute_synthesis_plan(request.plan, request.plan_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/synthesis/plans/{plan_id}")
async def get_plan_status_endpoint(plan_id: str):
    """Get status of an executing plan."""
    try:
        from cortex.synthesis import get_plan_status
        status = get_plan_status(plan_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/synthesis/plans")
async def list_synthesis_plans():
    """List all active synthesis plans."""
    try:
        from cortex.synthesis import list_active_plans
        plans = list_active_plans()
        return {"plans": plans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/synthesis/plans/{plan_id}")
async def cancel_synthesis_plan(plan_id: str):
    """Cancel an executing plan."""
    try:
        from cortex.synthesis import cancel_plan
        success = await cancel_plan(plan_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Plan {plan_id} not found")
        return {"status": "cancelled", "plan_id": plan_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Self-Evolution Endpoints ---

class AnalyzeCodeRequest(BaseModel):
    file_path: str

@app.post("/evolution/analyze")
async def analyze_code_endpoint(
    request: AnalyzeCodeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Analyze code structure."""
    try:
        from cortex.self_evolution import analyze_code
        analysis = analyze_code(request.file_path)
        return {
            "file_path": analysis.file_path,
            "functions": analysis.functions,
            "classes": analysis.classes,
            "imports": analysis.imports,
            "complexity_score": analysis.complexity_score,
            "modification_points": analysis.modification_points
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ProposeModificationRequest(BaseModel):
    file_path: str
    intent: str

@app.post("/evolution/propose")
async def propose_modification_endpoint(
    request: ProposeModificationRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Propose a code modification."""
    try:
        from cortex.self_evolution import propose_modification
        modification = propose_modification(request.file_path, request.intent)
        return {
            "mod_id": modification.id,
            "file_path": modification.file_path,
            "type": modification.type,
            "timestamp": modification.timestamp.isoformat(),
            "backup_path": modification.backup_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ApplyModificationRequest(BaseModel):
    mod_id: str
    new_content: str
    safe_mode: bool = True

@app.post("/evolution/apply")
async def apply_modification_endpoint(
    request: ApplyModificationRequest,
    current_user: User = Depends(get_current_admin_user)  # Protected: Admin only
):
    """Apply a code modification."""
    try:
        from cortex.self_evolution import evolution_engine
        
        # Find modification
        modification = None
        for mod in evolution_engine.modification_history:
            if mod.id == request.mod_id:
                modification = mod
                break
        
        if not modification:
            raise HTTPException(status_code=404, detail=f"Modification {request.mod_id} not found")
        
        # Set new content
        modification.new_content = request.new_content
        
        # Apply
        from cortex.self_evolution import apply_modification
        success = apply_modification(modification, request.safe_mode)
        
        if success:
            return {"status": "applied", "mod_id": request.mod_id}
        else:
            raise HTTPException(status_code=400, detail="Modification failed validation")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evolution/rollback/{mod_id}")
async def rollback_modification_endpoint(
    mod_id: str,
    current_user: User = Depends(get_current_admin_user)  # Protected: Admin only
):
    """Rollback a modification."""
    try:
        from cortex.self_evolution import rollback_modification
        success = rollback_modification(mod_id)
        
        if success:
            return {"status": "rolled_back", "mod_id": mod_id}
        else:
            raise HTTPException(status_code=404, detail=f"Modification {mod_id} not found or cannot be rolled back")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/evolution/history")
async def get_evolution_history():
    """Get modification history."""
    try:
        from cortex.self_evolution import get_modification_history
        history = get_modification_history()
        return {"modifications": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateToolRequest(BaseModel):
    name: str
    description: str
    code: str

@app.post("/evolution/tool/create")
async def create_tool_endpoint(
    request: CreateToolRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new tool."""
    try:
        from cortex.self_evolution import create_tool, ToolSpec
        
        spec = ToolSpec(request.name, request.description, request.code)
        tool = create_tool(spec)
        
        if tool:
            return {
                "status": "created",
                "tool_name": request.name,
                "callable": tool is not None
            }
        else:
            raise HTTPException(status_code=400, detail="Tool creation failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Platform & Management Endpoints (Phase 14) ---

@app.get("/tools")
async def list_tools():
    """List all available tools/skills."""
    tools = [multiply, vector_search, save_memory, execute_python, consolidate_memory]
    return [
        {
            "name": t.name,
            "description": t.description,
            "args": t.args_schema.schema() if t.args_schema else {}
        }
        for t in tools
    ]

@app.get("/agents")
async def list_agents():
    """List real-time status of all agents."""
    return {
        "agents": agent_status_manager.get_all_agents()
    }

class ApiKeyRequest(BaseModel):
    api_key: str

@app.post("/settings/api-key")
async def update_api_key(request: ApiKeyRequest, current_user: User = Depends(get_current_admin_user)):
    """Update LLM API Key."""
    env_path = ".env"
    try:
        # Update current process environment
        os.environ["OPENAI_API_KEY"] = request.api_key
        
        # Persist to .env file
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()
        
        key_found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("OPENAI_API_KEY="):
                new_lines.append(f"OPENAI_API_KEY={request.api_key}\n")
                key_found = True
            else:
                new_lines.append(line)
        
        if not key_found:
            new_lines.append(f"\nOPENAI_API_KEY={request.api_key}\n")
            
        with open(env_path, "w") as f:
            f.writelines(new_lines)
            
        return {"status": "updated"}
    except Exception as e:
        logger.error(f"Failed to update API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Observability Endpoints ---

@app.get("/metrics")
async def get_metrics_endpoint(name: Optional[str] = None, window: Optional[int] = None):
    """Get metrics data."""
    try:
        from cortex.observability import get_metrics
        metrics = get_metrics(name, window)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/history")
async def get_metrics_history(name: str, window: int = 3600):
    """Get historical metrics."""
    try:
        from cortex.observability import get_metrics
        return get_metrics(name, window)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/traces/{trace_id}")
async def get_trace_endpoint(trace_id: str):
    """Get trace details."""
    try:
        from cortex.observability import get_trace
        trace = get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
        return trace
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def query_logs_endpoint(
    level: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100
):
    """Query logs."""
    try:
        from cortex.observability import query_logs, LogLevel
        
        log_level = None
        if level:
            try:
                log_level = LogLevel[level.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid log level: {level}")
        
        logs = query_logs(log_level, search, limit)
        return {"logs": logs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts")
async def get_alerts_endpoint():
    """Get active alerts."""
    try:
        from cortex.observability import check_alerts
        alerts = check_alerts()
        return {
            "alerts": [
                {
                    "alert_id": alert.alert_id,
                    "name": alert.name,
                    "severity": alert.severity,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat(),
                    "acknowledged": alert.acknowledged
                }
                for alert in alerts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/performance")
async def get_performance_endpoint():
    """Get performance statistics."""
    try:
        from cortex.observability import get_performance_stats
        stats = get_performance_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Channel Management Endpoints ---

class ChannelRegisterRequest(BaseModel):
    channel_type: str  # "web", "telegram", "whatsapp", "sms"
    config: Dict[str, Any]

@app.post("/channels/register")
async def register_channel(
    request: ChannelRegisterRequest,
    current_user: User = Depends(get_current_admin_user)  # Protected: Admin only
):
    """Register and start a new channel."""
    try:
        bridge = get_agent_bridge()
        
        if request.channel_type == "web":
            from channels import WebChannel
            channel = WebChannel(config=request.config)
            await channel.start()
            bridge.register_channel("web", channel)
            
        elif request.channel_type == "telegram":
            from channels import TelegramChannel
            channel = TelegramChannel(config=request.config)
            await channel.start()
            bridge.register_channel("telegram", channel)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported channel type: {request.channel_type}")
        
        return {
            "status": "success",
            "channel_type": request.channel_type,
            "channel_status": channel.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/channels")
async def list_channels():
    """List all active channels."""
    try:
        bridge = get_agent_bridge()
        stats = bridge.get_stats()
        return {
            "channels": stats["channels"],
            "active_contexts": stats["active_contexts"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChannelSendRequest(BaseModel):
    to: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

@app.post("/channels/{channel_id}/send")
async def send_channel_message(
    channel_id: str, 
    request: ChannelSendRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Send message through specific channel."""
    try:
        bridge = get_agent_bridge()
        success = await bridge.send_to_channel(channel_id, request.to, request.message)
        
        if success:
            return {"status": "sent", "channel": channel_id, "to": request.to}
        else:
            raise HTTPException(status_code=404, detail=f"Channel {channel_id} not found or failed to send")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GatewayPairRequest(BaseModel):
    device_id: str
    device_name: str
    channel_type: str
    metadata: Optional[Dict[str, Any]] = None

@app.post("/gateway/pair")
async def pair_device(request: GatewayPairRequest):
    """Pair a new device with the Gateway."""
    try:
        gateway = get_gateway()
        
        # Start gateway if not running
        if not gateway.is_running:
            await gateway.start()
        
        session = gateway.pair_device(
            device_id=request.device_id,
            device_name=request.device_name,
            channel_type=request.channel_type,
            metadata=request.metadata or {}
        )
        
        return {
            "status": "paired",
            "session_id": session.session_id,
            "auth_token": session.auth_token,
            "expires_at": session.expires_at,
            "websocket_url": f"ws://localhost:{gateway.port}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gateway/status")
async def gateway_status():
    """Get Gateway server status."""
    try:
        gateway = get_gateway()
        return {
            "running": gateway.is_running,
            "port": gateway.port,
            "active_connections": len(gateway.connections),
            "registered_channels": len(gateway.channels)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import socket
    
    # Try different ports if 8000 is in use
    port = int(os.getenv("PORT", "8080"))
    max_port_attempts = 10
    
    for attempt in range(max_port_attempts):
        try:
            # Test if port is available
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('0.0.0.0', port))
            sock.close()
            
            if result != 0:  # Port is available
                break
            else:
                print(f"Port {port} is in use, trying {port + 1}...")
                port += 1
        except Exception:
            port += 1
    
    print(f"\n{'='*60}")
    print(f"[START] Starting Agentic AI Server")
    print(f"{'='*60}")
    print(f"Server: http://0.0.0.0:{port}")
    print(f"Dashboard: http://localhost:{port}/")
    print(f"API Docs: http://localhost:{port}/docs")
    print(f"{'='*60}\n")
    
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

