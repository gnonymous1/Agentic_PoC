import asyncio
from typing import List, Dict, Any
from agents.base_agent import BaseAgent, SubAgentTask
from agent_fabric.tool_loader import load_dynamic_tools
from security.sandbox import ExecutionSandbox

class DynamicToolAgent(BaseAgent):
    """
    An agent that dynamically loads and exposes third-party tools.
    Allows for runtime expansion of OMNIOS capabilities.
    """

    def __init__(self, config: dict, name: str):
        super().__init__(config, name)
        self.sandbox = ExecutionSandbox()

    def _register_sub_agents(self):
        # Load tools from the dynamic_tools directory
        dynamic_tools = load_dynamic_tools()
        
        for tool in dynamic_tools:
            # Wrap LangChain-style tools into SubAgentTasks
            # Assuming tool has .name, .description, and is callable
            task_name = getattr(tool, "name", tool.__name__ if hasattr(tool, "__name__") else str(tool))
            
            self.sub_agents[task_name] = SubAgentTask(
                name=task_name,
                handler=self._wrap_tool(tool),
                description=getattr(tool, "description", "Dynamic tool"),
                capabilities=[task_name]
            )

    def _wrap_tool(self, tool):
        async def handler(params: dict) -> dict:
            # LangChain tools usually take a single string or kwargs
            try:
                # Wrap execution in sandbox
                sb_result = self.sandbox.run_safe(tool, params)
                
                if sb_result["success"]:
                    return {"status": "success", "result": sb_result["result"], "stdout": sb_result["stdout"]}
                else:
                    return {"status": "error", "message": sb_result["error"]}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return handler

    def get_capabilities(self) -> List[str]:
        capabilities = []
        for sub_agent in self.sub_agents.values():
            capabilities.extend(sub_agent.capabilities)
        return capabilities
