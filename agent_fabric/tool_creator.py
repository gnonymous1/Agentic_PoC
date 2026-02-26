from langchain_core.tools import tool
from typing import Annotated
import os

TOOL_REGISTRY_PATH = "agent_fabric/dynamic_tools"

@tool
def create_new_tool(name: Annotated[str, "Name of the tool"], 
                    code: Annotated[str, "Python code for the tool function"]) -> str:
    """
    Creates a new tool by writing a python file to the dynamic tool registry.
    The code must contain a function decorated with @tool.
    """
    try:
        if not os.path.exists(TOOL_REGISTRY_PATH):
            os.makedirs(TOOL_REGISTRY_PATH)
            
        filename = f"{name}.py"
        filepath = os.path.join(TOOL_REGISTRY_PATH, filename)
        
        # Add imports if missing
        imports = "from langchain_core.tools import tool\nfrom typing import Annotated\n\n"
        full_code = imports + code if "from langchain_core.tools import tool" not in code else code
        
        with open(filepath, "w") as f:
            f.write(full_code)
            
        return f"Tool '{name}' created at {filepath}. usage: Import it dynamically."
    except Exception as e:
        return f"Failed to create tool: {e}"
