
import os
import importlib.util
import inspect
from langchain_core.tools import tool
from utils.logger import setup_logging

logger = setup_logging()

DYNAMIC_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "dynamic_tools")

def load_dynamic_tools():
    """
    Scans the dynamic_tools directory and returns a list of LangChain tools.
    """
    tools = []
    if not os.path.exists(DYNAMIC_TOOLS_DIR):
        os.makedirs(DYNAMIC_TOOLS_DIR)
        return tools

    for filename in os.listdir(DYNAMIC_TOOLS_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            module_name = filename[:-3]
            file_path = os.path.join(DYNAMIC_TOOLS_DIR, filename)
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for 'name' and 'description' metadata at module level
                module_tool_name = getattr(module, "name", None)
                module_tool_desc = getattr(module, "description", None)

                # Find functions and wrap them as proper LangChain tools
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) and not name.startswith("_"):
                        # Check if already a proper LangChain tool
                        if hasattr(obj, "item") and hasattr(obj, "func"):
                            # Already decorated with @tool
                            tools.append(obj)
                            logger.info(f"[ToolLoader] Registered dynamic tool (LangChain): {name} from {filename}")
                        elif callable(obj):
                            # Wrap plain function as a LangChain tool
                            try:
                                # Wrap plain function as a LangChain tool using StructuredTool
                                from langchain_core.tools import StructuredTool
                                from pydantic import BaseModel, Field
                                
                                # Create args schema dynamically
                                sig = inspect.signature(obj)
                                fields = {}
                                for param_name, param in sig.parameters.items():
                                    if param.default != inspect.Parameter.empty:
                                        fields[param_name] = (type(param.default), Field(default=param.default))
                                    else:
                                        fields[param_name] = (str, Field(description=f"Parameter {param_name}"))
                                
                                if fields:
                                    ArgsSchema = type(f'{name}Args', (BaseModel,), {
                                        '__annotations__': {k: v[0] for k, v in fields.items()},
                                        **{k: v[1] for k, v in fields.items()}
                                    })
                                else:
                                    ArgsSchema = None
                                
                                wrapped_tool = StructuredTool.from_function(
                                    func=obj,
                                    name=module_tool_name or name,
                                    description=module_tool_desc or obj.__doc__ or "Dynamic tool",
                                    args_schema=ArgsSchema
                                )
                                tools.append(wrapped_tool)
                                logger.info(f"[ToolLoader] Registered dynamic tool: {wrapped_tool.name} from {filename}")
                            except Exception as wrap_error:
                                logger.error(f"[ToolLoader] Failed to wrap tool {name} from {filename}: {wrap_error}")

            except Exception as e:
                logger.error(f"[ToolLoader] Error loading {filename}: {e}")
                
    return tools
