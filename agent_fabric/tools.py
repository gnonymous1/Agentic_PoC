from langchain_core.tools import tool
from typing import Annotated
from hippocampus.memory import Hippocampus
from utils.logger import setup_logging

logger = setup_logging()

# Initialize global memory instance
memory_system = Hippocampus()

@tool
def multiply(a: Annotated[int, "first number"], b: Annotated[int, "second number"]) -> int:
    """Multiplies two numbers."""
    try:
        result = a * b
        logger.info(f"Tool 'multiply' executed: {a} * {b} = {result}")
        return result
    except Exception as e:
        logger.error(f"Tool 'multiply' failed: {str(e)}")
        raise e

@tool
def vector_search(query: Annotated[str, "The query to search in memory"]) -> str:
    """
    Searches the internal knowledge base (Long-term memory) for relevant information.
    """
    try:
        logger.info(f"Tool 'vector_search' executed with query: {query}")
        results = memory_system.recall(query)
        if not results:
            return "No relevant memories found."
        
        formatted = "\n".join([f"- {r['content']} (Meta: {r['meta']})" for r in results])
        return formatted
    except Exception as e:
        logger.error(f"Tool 'vector_search' failed: {str(e)}")
        return f"Error searching memory: {str(e)}"

@tool
def save_memory(content: Annotated[str, "The information to save"], source: Annotated[str, "Source/Origin"] = "user") -> str:
    """
    Saves a piece of information to long-term memory.
    """
    try:
        logger.info(f"Tool 'save_memory' executed. Content length: {len(content)}")
        memory_system.remember(content, {"source": source})
        return "Memory saved successfully."
    except Exception as e:
        logger.error(f"Tool 'save_memory' failed: {str(e)}")
        return f"Error saving memory: {str(e)}"

@tool
def execute_python(code: Annotated[str, "The python code to execute"]) -> str:
    """
    Executes python code in a separate process.
    WARNING: This executes code directly on the host machine.
    """
    import subprocess
    import sys
    import os
    
    # Write code to a temporary file
    temp_filename = "temp_execution.py"
    with open(temp_filename, "w", encoding="utf-8") as f:
        f.write(code)
        
    try:
        logger.info(f"Executing Python code: {code[:50]}...")
        # Execute the code
        result = subprocess.run(
            [sys.executable, temp_filename],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        
        output = result.stdout
        error = result.stderr
        
        return_msg = f"Executed code:\n{code}\n"
        if output:
            return_msg += f"\nOutput:\n{output}"
        if error:
            return_msg += f"\nErrors:\n{error}"
        if result.returncode != 0:
            return_msg += f"\nExit Code: {result.returncode}"
            
        return return_msg
        
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (30s limit)"
    except Exception as e:
        return f"Error executing code: {str(e)}"
    finally:
        # Cleanup
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@tool
def consolidate_memory() -> str:
    """
    The 'Dream Layer'. Fetches recent memories and distills them into long-term knowledge.
    """
    try:
        logger.info("Tool 'consolidate_memory' executed.")
        result = memory_system.consolidate()
        return f"Consolidation result: {result}"
    except Exception as e:
        logger.error(f"Tool 'consolidate_memory' failed: {str(e)}")
        return f"Error consolidating memory: {str(e)}"
