from langchain_core.tools import tool
from typing import Annotated
from hippocampus.memory import Hippocampus
from utils.logger import setup_logging
import sys
import io
import contextlib
import multiprocessing

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

def _restricted_execute(code, result_queue):
    """
    Executes code in a restricted environment.
    This function is intended to run in a separate process.
    """
    # Capture stdout/stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    # Define allowed built-ins
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin, "bool": bool,
        "bytearray": bytearray, "bytes": bytes, "callable": callable, "chr": chr,
        "complex": complex, "dict": dict, "divmod": divmod, "enumerate": enumerate,
        "filter": filter, "float": float, "format": format, "frozenset": frozenset,
        "getattr": getattr, "hasattr": hasattr, "hash": hash, "hex": hex, "id": id,
        "int": int, "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
        "len": len, "list": list, "map": map, "max": max, "min": min, "next": next,
        "object": object, "oct": oct, "ord": ord, "pow": pow, "print": print,
        "range": range, "repr": repr, "reversed": reversed, "round": round,
        "set": set, "slice": slice, "sorted": sorted, "str": str, "sum": sum,
        "tuple": tuple, "type": type, "zip": zip,
        # Exceptions
        "BaseException": BaseException, "Exception": Exception, "ArithmeticError": ArithmeticError,
        "BufferError": BufferError, "LookupError": LookupError, "AssertionError": AssertionError,
        "AttributeError": AttributeError, "EOFError": EOFError, "FloatingPointError": FloatingPointError,
        "GeneratorExit": GeneratorExit, "ImportError": ImportError, "ModuleNotFoundError": ModuleNotFoundError,
        "IndexError": IndexError, "KeyError": KeyError, "KeyboardInterrupt": KeyboardInterrupt,
        "MemoryError": MemoryError, "NameError": NameError, "NotImplementedError": NotImplementedError,
        "OSError": OSError, "OverflowError": OverflowError, "RecursionError": RecursionError,
        "ReferenceError": ReferenceError, "RuntimeError": RuntimeError, "StopIteration": StopIteration,
        "StopAsyncIteration": StopAsyncIteration, "SyntaxError": SyntaxError, "IndentationError": IndentationError,
        "TabError": TabError, "SystemError": SystemError, "SystemExit": SystemExit, "TypeError": TypeError,
        "UnboundLocalError": UnboundLocalError, "UnicodeError": UnicodeError, "UnicodeEncodeError": UnicodeEncodeError,
        "UnicodeDecodeError": UnicodeDecodeError, "UnicodeTranslateError": UnicodeTranslateError, "ValueError": ValueError,
        "ZeroDivisionError": ZeroDivisionError
    }

    # Define allowed modules
    allowed_modules = {
        "math", "random", "datetime", "json", "time", "re", "string", "collections", "itertools", "functools"
    }

    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in allowed_modules:
            return __import__(name, globals, locals, fromlist, level)
        raise ImportError(f"Import of module '{name}' is restricted.")

    # Add custom import to builtins so 'import' statements work
    safe_builtins["__import__"] = restricted_import

    # Create restricted globals
    # We assign safe_builtins to __builtins__
    restricted_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
    }

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(stderr_capture):
            exec(code, restricted_globals)

        result_queue.put({
            "success": True,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue()
        })
    except Exception as e:
        # Instead of just str(e), we can format it to match expected "Error Type: Message"
        error_msg = f"{type(e).__name__}: {str(e)}"
        result_queue.put({
            "success": False,
            "stdout": stdout_capture.getvalue(),
            "stderr": stderr_capture.getvalue(),
            "error": error_msg
        })

@tool
def execute_python(code: Annotated[str, "The python code to execute"]) -> str:
    """
    Executes python code in a secure, restricted environment.
    Only allows safe operations and standard libraries (math, random, datetime, etc.).
    File system access, network, and dangerous built-ins are BLOCKED.
    """
    logger.info(f"Executing Python code (secure): {code[:50]}...")

    # Use multiprocessing to isolate execution and handle timeouts reliably
    # This also helps prevent global state pollution
    result_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=_restricted_execute, args=(code, result_queue))
    
    try:
        process.start()
        process.join(timeout=30)  # 30 second timeout
        
        if process.is_alive():
            process.terminate()
            process.join()
            return "Error: Execution timed out (30s limit)"
        
        if not result_queue.empty():
            result = result_queue.get()

            output = result["stdout"]
            error = result["stderr"]

            return_msg = f"Executed code:\n{code}\n"
            if output:
                return_msg += f"\nOutput:\n{output}"
            if error:
                return_msg += f"\nErrors:\n{error}"

            if not result["success"]:
                 # Append the exception message to Errors section if possible, or create it
                 exception_msg = result.get('error', 'Unknown error')
                 if "Errors:" not in return_msg:
                     return_msg += f"\nErrors:\n{exception_msg}"
                 else:
                     return_msg += f"\n{exception_msg}"

            return return_msg
        else:
            return "Error: No result returned from execution process."
            
    except Exception as e:
        logger.error(f"Tool 'execute_python' failed: {str(e)}")
        return f"Error executing code: {str(e)}"

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
