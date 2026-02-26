# Facade to maintain backward compatibility and export new skills
from agent_fabric.skills.system.file_ops import list_files_recursive, grep_search, system_info
from agent_fabric.skills.network.net_tools import ping_host, curl_request
from agent_fabric.skills.coding.dev_tools import execute_python_code, git_clone
from agent_fabric.skills.data.data_tools import analyze_csv, web_scrape
from agent_fabric.skills.productivity.metrics import calculate_efficiency

# Legacy tools re-export or re-implement
from langchain_core.tools import tool
from typing import Annotated
from hippocampus.memory import Hippocampus
from utils.logger import setup_logging

logger = setup_logging()
memory_system = Hippocampus()

@tool
def multiply(a: Annotated[int, "first number"], b: Annotated[int, "second number"]) -> int:
    """Multiplies two numbers."""
    return a * b

@tool
def vector_search(query: Annotated[str, "The query to search in memory"]) -> str:
    """Searches memory."""
    results = memory_system.recall(query)
    if not results: return "No results."
    return str(results)

@tool
def save_memory(content: Annotated[str, "Content to save"]) -> str:
    """Saves to memory."""
    memory_system.remember(content)
    return "Saved."

@tool
def execute_python(code: Annotated[str, "Code to execute"]) -> str:
    """Legacy wrapper for execute_python_code."""
    return execute_python_code(code)

@tool
def consolidate_memory() -> str:
    """Consolidates memory."""
    return str(memory_system.consolidate())

# Export all tools as a list for easy registration
ALL_TOOLS = [
    list_files_recursive, grep_search, system_info,
    ping_host, curl_request,
    execute_python_code, git_clone,
    analyze_csv, web_scrape,
    calculate_efficiency,
    multiply, vector_search, save_memory, execute_python, consolidate_memory
]
