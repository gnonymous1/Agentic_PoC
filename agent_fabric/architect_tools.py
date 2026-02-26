import os
from typing import Annotated, List
from langchain_core.tools import tool
from utils.logger import setup_logging

logger = setup_logging()

WORKING_DIR = os.getcwd() # Restrict to current working dir for safety in PoC

@tool
def list_files(path: Annotated[str, "The directory path to list"] = ".") -> str:
    """
    Lists files in a directory. Relative paths are relative to the project root.
    """
    try:
        abs_path = os.path.abspath(os.path.join(WORKING_DIR, path))
        if not abs_path.startswith(WORKING_DIR):
            return "Error: Access denied (Outside project root)"
        
        files = os.listdir(abs_path)
        return f"Files in {path}: {files}"
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def read_file(file_path: Annotated[str, "The path to the file to read"]) -> str:
    """
    Reads the content of a file.
    """
    try:
        abs_path = os.path.abspath(os.path.join(WORKING_DIR, file_path))
        if not abs_path.startswith(WORKING_DIR):
            return "Error: Access denied (Outside project root)"
            
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def write_file(file_path: Annotated[str, "The path to the file to write"], content: Annotated[str, "The content to write"]) -> str:
    """
    Writes content to a file. Overwrites if exists.
    """
    try:
        abs_path = os.path.abspath(os.path.join(WORKING_DIR, file_path))
        if not abs_path.startswith(WORKING_DIR):
            return "Error: Access denied (Outside project root)"
            
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
def create_new_tool(tool_name: Annotated[str, "Snake_case name of the tool (e.g. 'get_weather')"], code: Annotated[str, "Complete Python code for the tool, including imports and @tool decorator"]) -> str:
    """
    Creates a new tool that the agent can use immediately. 
    The code MUST include `from langchain_core.tools import tool` and use the `@tool` decorator.
    Example:
    @tool
    def my_new_tool(arg: str) -> str:
        \"\"\"Docstring here.\"\"\"
        return f"Processed {arg}"
    """
    try:
        dynamic_dir = os.path.join(WORKING_DIR, "agent_fabric", "dynamic_tools")
        if not os.path.exists(dynamic_dir):
            os.makedirs(dynamic_dir)
            
        file_path = os.path.join(dynamic_dir, f"{tool_name}.py")
        if "from langchain_core.tools import tool" not in code:
             code = "from langchain_core.tools import tool\n\n" + code
             
        # Also ensure Annotated is available if used
        if "Annotated" in code and "from typing" not in code:
             code = "from typing import Annotated\n" + code

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
            
        logger.info(f"Created new tool: {tool_name}")
        return f"Tool '{tool_name}' created successfully. I can use it after the next turn."
    except Exception as e:
        return f"Error creating tool: {str(e)}"
