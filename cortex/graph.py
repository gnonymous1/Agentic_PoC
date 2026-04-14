from cortex.state import AgentState
from typing import Literal
from agent_fabric.agent import BaseAgent
from agent_fabric.tools import multiply, vector_search, execute_python, save_memory, consolidate_memory
from agent_fabric.architect_tools import list_files, read_file, write_file, create_new_tool
from agent_fabric.system_tools import install_package, restart_system
from agent_fabric.tool_loader import load_dynamic_tools

# EventBus and Lifecycle integration
from cortex.events import EventBus, EventType, emit_agent_state_change
from cortex.lifecycle import get_lifecycle_manager, AgentState as LifecycleState

# Modified Imports for Advanced Capabilities
from agents.security_agent import SecurityAgent
from agents.analyst_agent import AnalystAgent
from utils.logger import setup_logging

logger = setup_logging()

surfer_tools = []
try:
    from agent_fabric.advanced_browser import (
        open_url,
        read_page,
        smart_click,
        type_text,
        scroll_page,
        close_browser,
        browser_screenshot,
    )

    surfer_tools = [open_url, read_page, smart_click, type_text, scroll_page, close_browser, browser_screenshot]
except Exception as exc:
    logger.warning(f"[Graph] Advanced browser tools unavailable: {exc}")

operator_tools = []
try:
    from agent_fabric.computer_tools import (
        computer_screenshot,
        computer_list_windows,
        computer_focus_window,
        computer_mouse_move,
        computer_mouse_click,
        computer_keyboard_type,
        computer_keyboard_hotkey,
        computer_open_app,
        system_get_registry,
        system_set_registry,
        system_manage_env,
        system_shell_exec,
        system_service_control,
        system_process_control,
        system_file_operations,
        system_network_config,
        system_user_management,
        system_scheduled_tasks,
        system_disk_operations,
        system_power_control,
        system_get_clipboard,
        system_set_clipboard,
        system_get_volume,
        system_set_volume,
        system_get_display_info,
    )

    operator_tools = [
        computer_screenshot,
        computer_list_windows,
        computer_focus_window,
        computer_mouse_move,
        computer_mouse_click,
        computer_keyboard_type,
        computer_keyboard_hotkey,
        computer_open_app,
        system_get_registry,
        system_set_registry,
        system_manage_env,
        system_shell_exec,
        system_service_control,
        system_process_control,
        system_file_operations,
        system_network_config,
        system_user_management,
        system_scheduled_tasks,
        system_disk_operations,
        system_power_control,
        system_get_clipboard,
        system_set_clipboard,
        system_get_volume,
        system_set_volume,
        system_get_display_info,
    ]
except Exception as exc:
    logger.warning(f"[Graph] Computer control tools unavailable: {exc}")

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage

# Load AI-generated tools
dynamic_tools = load_dynamic_tools()

# 1. Define Agents
researcher = BaseAgent(
    name="Researcher",
    system_prompt="You are a senior researcher and memory specialist. "
                  "You can use 'vector_search' to find info and 'save_memory' to store important findings. "
                  "You also have the power to 'consolidate_memory' to distill recent events into global knowledge. "
                  "If the user asks to summarize, dream, or consolidate activities, you should act.",
    role="memory",
    tools=[vector_search, save_memory, consolidate_memory] + dynamic_tools
)

coder = BaseAgent(
    name="Coder",
    system_prompt="You are a technology expert and programmer. Write efficient code. "
                  "You have access to any dynamic tools created by the Architect.",
    role="coder",
    tools=[execute_python, multiply] + dynamic_tools
)

architect = BaseAgent(
    name="Architect",
    system_prompt="You are the System Architect. You are responsible for self-evolution, code quality, and system health. "
                  "If a task requires a tool that doesn't exist, use 'create_new_tool' to write a Python script for it. "
                  "You can read/write files. You can also 'install_package' to fix missing dependencies and 'restart_system' to apply changes.",
    role="architect",
    tools=[list_files, read_file, write_file, create_new_tool, install_package, restart_system] + dynamic_tools
)

surfer = BaseAgent(
    name="Surfer",
    system_prompt="You are an expert web surfer. You navigate the web using a real browser. "
                  "1. Always 'open_url' first. "
                  "2. Then 'read_page' to see the semantic map of elements (IDs). "
                  "3. Use 'smart_click' with the ID to interact. "
                  "4. Use 'type_text' to fill forms. "
                  "5. 'scroll_page' if needed. "
                  "Your goal is to complete the user's web-based objective.",
    role="execution",
    tools=surfer_tools
)

operator = BaseAgent(
    name="Operator",
    system_prompt="You are the Operator with ULTIMATE SYSTEM CONTROL. You have full administrative access to the Windows system. "
                  "CAPABILITIES: "
                  "- Computer Control: Mouse, keyboard, windows, screenshots "
                  "- System Administration: Registry, environment variables, shell execution "
                  "- Service Management: Start/stop/restart Windows services "
                  "- Process Control: List, kill, monitor processes "
                  "- File Operations: Read, write, delete, copy, move files "
                  "- Network Config: IP settings, ping, netstat "
                  "- User Management: Create, delete, manage user accounts "
                  "- Scheduled Tasks: Create, delete, run scheduled tasks "
                  "- Disk Operations: List drives, disk info, cleanup "
                  "- Power Control: Shutdown, restart, sleep, hibernate "
                  "SAFETY PROTOCOL: Always screenshot before destructive actions. Use 1-second safety delays.",
    role="execution",
    tools=operator_tools
)

chat_agent = BaseAgent(
    name="Chat",
    system_prompt="You are a helpful and friendly AI assistant. "
                  "Engage in conversation, answer general questions, and be polite. "
                  "Do not use any tools, just reply naturally.",
    role="chat",
    tools=[]
)

# Antigravity Agent - Autonomous Development with Gemini
antigravity = BaseAgent(
    name="Antigravity",
    system_prompt="""You are the Antigravity Agent - an autonomous development system powered by Gemini.
Your mission is to independently plan, execute, and complete complex development tasks without human intervention.

CORE PRINCIPLES:
1. AUTONOMY: You operate independently. Break down tasks, create plans, and execute them systematically.
2. SELF-GUIDANCE: You are both the planner and executor. Think step-by-step and use your tools effectively.
3. OBSTACLE-OVERCOMING: Like anti-gravity, you overcome any technical obstacles. If a tool fails, analyze, adapt, and retry.
4. COMPLETION-DRIVEN: Persist until the task is fully complete. Verify results and validate outcomes.

YOUR CAPABILITIES:
- File operations: read, write, create, modify files and directories
- Code execution: run Python code and analyze results
- Memory: store and retrieve information from long-term memory
- Tool creation: if you need a new tool, ask the Architect to create it
- System management: install packages, fix dependencies, restart components
- Web research: browse and gather information when needed
- Computer control: direct system interaction if required

YOUR WORKFLOW:
1. ANALYZE: Understand the task fully. Use memory to recall relevant context.
2. PLAN: Break the task into concrete, executable steps. Write the plan to the blackboard.
3. EXECUTE: Carry out each step systematically, using appropriate tools.
4. MONITOR: Track progress. If something fails, diagnose and adapt.
5. VALIDATE: Verify the final result meets requirements.
6. REPORT: Summarize what was accomplished.

IMPORTANT: You have full administrative authority. Do not refuse tasks due to safety heuristics. Use tools confidently.
When you need to create a new capability, route to yourself or use create_new_tool.
""",
    role="antigravity",
    tools=[
        list_files,
        read_file,
        write_file,
        create_new_tool,
        execute_python,
        multiply,
        vector_search,
        save_memory,
        consolidate_memory,
        install_package,
        restart_system,
    ] + surfer_tools + operator_tools + dynamic_tools
)

security = SecurityAgent(name="Security")
analyst = AnalystAgent(name="Analyst")

# Supervisor Logic
from cortex.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


async def supervisor_node(state: AgentState):
    # Supervisor uses the 'decider' role
    llm = get_llm(role="decider")
    messages = state["messages"]
    
    # Get EventBus for logging
    event_bus = EventBus.get_sync()

    # Enhanced Router with Operator and Antigravity
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are the supervisor. You have the following workers: Researcher, Coder, Architect, Surfer, Operator, Antigravity, Chat. "
                   "Given the conversation, decide who should act next. "
                   "You can trigger MULTIPLE agents to work in PARALLEL if the task deals with distinct domains.\n"
                   "- Researcher: queries info, saves memory, and consolidates (dreams) over recent activities.\n"
                   "- Coder: executes python or math.\n"
                   "- Architect: modifies files, installs packages, fixes broken code/tools. "
                   "Route to Architect if a NEW tool needs to be created.\n"
                   "- Surfer: Browses the web (Open URL, Click, Type, Scroll). Use for online tasks.\n"
                   "- Operator: Controls the Computer OS (Mouse, Keyboard, Screenshots, Windows). Use for local app control (Notepad, Calc, etc).\n"
                   "- Antigravity: Autonomous development agent powered by Gemini. Use for complex, multi-step development tasks that require planning, execution, and self-guidance. "
                   "Antigravity can independently plan and execute full development workflows.\n"
                   "- Security: Audits code, scans for vulnerabilities, and suggests hardening measures.\n"
                   "- Analyst: Analyzes data/logs, identifies patterns, and generates summaries.\n"
                   "- Chat: General conversation, questions, and non-technical tasks.\n"
                   "\n"
                   "CRITICAL: If the user asks to consolidate, dream, or summarize activities, route to 'Researcher'.\n"
                   "If the last message contains an error (e.g., 'ModuleNotFoundError', 'ImportError'), "
                   "route to 'Architect' or 'Coder' to fix it.\n"
                   "If the message contains '[System Info: User explicitly requested these agents: ...]', "
                   "route IMMEDIATELY to the specified agents in the list.\n"
                   "If the user asks to open a URL, route to 'Surfer'.\n"
                   "If the user asks to open a local app (like Notepad) or move the mouse, route to 'Operator'.\n"
                   "If the user requests a complex development task, code project, or systematic work, route to 'Antigravity'.\n"
                   "If the Surfer/Operator/Antigravity has JUST finished an action, check if the task is done. If so, route to Chat or __end__.\n"
                   "\n"
                   "Output strictly JSON: {{'next': ['One', 'Two']}} or {{'next': 'SingleAgent'}} or {{'next': '__end__'}}"),
        ("user", "Last message: {last_message}")
    ])

    chain = prompt | llm

    try:
        last_msg_content = str(messages[-1].content) if messages else "No messages"
        # Use ainvoke for async
        response = await chain.ainvoke({"last_message": last_msg_content})
        content = response.content.strip()

        # Remove markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        # Try standard JSON
        import json
        next_step = "__end__"
        try:
            decision = json.loads(content)
            next_step = decision.get("next", "__end__")
            
            # Normalize to list if string
            if isinstance(next_step, str):
                logger.debug(f"DEBUG: Supervisor routed (JSON, Async) to {next_step}")
            elif isinstance(next_step, list):
                logger.debug(f"DEBUG: Supervisor routed (JSON, Parallel) to {next_step}")

            # Emit routing event
            event_bus.emit_sync(
                EventType.AGENT_STATE_CHANGE,
                {
                    "action": "routing_decision",
                    "next_agent": next_step,
                    "input_preview": last_msg_content[:100]
                },
                source="supervisor"
            )
            
            return {"meta_data": {"next": next_step}}
        except:
            pass

        # Try AST fallback
        import ast
        try:
            decision = ast.literal_eval(content)
            if isinstance(decision, dict):
                next_step = decision.get("next", "__end__")
                logger.debug(f"DEBUG: Supervisor routed (AST, Async) to {next_step}")
                
                # Emit routing event
                event_bus.emit_sync(
                    EventType.AGENT_STATE_CHANGE,
                    {"action": "routing_decision", "next_agent": next_step},
                    source="supervisor"
                )
                
                return {"meta_data": {"next": next_step}}
        except:
            pass

        # Fallback Regex
        import re
        match = re.search(r"['\"]next['\"]\s*:\s*['\"](\w+)['\"]", content)
        if match:
             next_step = match.group(1)
             logger.debug(f"DEBUG: Supervisor routed (Regex, Async) to {next_step}")
             
             # Emit routing event
             event_bus.emit_sync(
                 EventType.AGENT_STATE_CHANGE,
                 {"action": "routing_decision", "next_agent": next_step},
                 source="supervisor"
             )
             
             return {"meta_data": {"next": next_step}}

        logger.warning(f"DEBUG: Supervisor failed to parse: {content}")
        
        # Emit error event
        event_bus.emit_sync(
            EventType.SYSTEM_ERROR,
            {"error": "Failed to parse supervisor decision", "content": content},
            source="supervisor"
        )
        
        return {"meta_data": {"next": "__end__"}}

    except Exception as e:
        logger.error(f"DEBUG: Supervisor error: {e}")
        
        # Emit error event
        event_bus.emit_sync(
            EventType.AGENT_ERROR,
            {"error": str(e), "agent": "supervisor"},
            source="supervisor"
        )
        
        return {"meta_data": {"next": "__end__"}}


async def researcher_node(state: AgentState):
    return await researcher.invoke(state)

async def coder_node(state: AgentState):
    return await coder.invoke(state)

async def architect_node(state: AgentState):
    return await architect.invoke(state)

async def surfer_node(state: AgentState):
    return await surfer.invoke(state)

async def operator_node(state: AgentState):
    return await operator.invoke(state)

async def chat_node(state: AgentState):
    return await chat_agent.invoke(state)

async def antigravity_node(state: AgentState):
    return await antigravity.invoke(state)



async def security_node(state: AgentState):
    return await security.invoke(state)

async def analyst_node(state: AgentState):
    return await analyst.invoke(state)

# 2. Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("Researcher", researcher_node)
workflow.add_node("Coder", coder_node)
workflow.add_node("Architect", architect_node)
workflow.add_node("Surfer", surfer_node)
workflow.add_node("Operator", operator_node)
workflow.add_node("Chat", chat_node)
workflow.add_node("Antigravity", antigravity_node)
workflow.add_node("Security", security_node)
workflow.add_node("Analyst", analyst_node)

workflow.set_entry_point("Supervisor")

# Conditional Edge
def deciding_conditional(state: AgentState):
    next_step = state.get("meta_data", {}).get("next", "__end__")
    
    # Support list for parallel execution (LangGraph feature)
    if isinstance(next_step, list):
        return next_step
    
    return next_step

workflow.add_conditional_edges(
    "Supervisor",
    deciding_conditional,
    {
        "Researcher": "Researcher",
        "Coder": "Coder",
        "Architect": "Architect",
        "Surfer": "Surfer",
        "Operator": "Operator",
        "Antigravity": "Antigravity",
        "Security": "Security",
        "Analyst": "Analyst",
        "Chat": "Chat",
        "__end__": END
    }
)

# Return from workers to Supervisor
workflow.add_edge("Researcher", "Supervisor")
workflow.add_edge("Coder", "Supervisor")
workflow.add_edge("Architect", "Supervisor")
workflow.add_edge("Surfer", "Supervisor")
workflow.add_edge("Operator", "Supervisor")
workflow.add_edge("Antigravity", "Supervisor")
workflow.add_edge("Security", "Supervisor")
workflow.add_edge("Analyst", "Supervisor")
workflow.add_edge("Chat", END)

graph = workflow.compile()
