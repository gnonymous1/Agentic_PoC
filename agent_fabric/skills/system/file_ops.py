from langchain_core.tools import tool
from typing import Annotated, List, Dict
import subprocess
import os
import shutil
from pathlib import Path

@tool
def list_files_recursive(path: Annotated[str, "Root directory to list"] = ".") -> str:
    """Lists all files recursively in a directory tree."""
    try:
        result = []
        for root, dirs, files in os.walk(path):
            level = root.replace(path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            result.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                result.append(f"{subindent}{f}")
        return "\n".join(result)
    except Exception as e:
        return f"Error listing files: {str(e)}"

@tool
def grep_search(pattern: Annotated[str, "Regex pattern to search"], path: Annotated[str, "Path to search in"] = ".") -> str:
    """Searches for a pattern in files using grep."""
    try:
        cmd = ["grep", "-r", pattern, path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.stdout else "No matches found."
    except Exception as e:
        return f"Error executing grep: {str(e)}"

@tool
def system_info() -> str:
    """Returns detailed system information (OS, CPU, Memory)."""
    import platform
    import psutil

    try:
        info = [
            f"OS: {platform.system()} {platform.release()}",
            f"Machine: {platform.machine()}",
            f"CPU Cores: {psutil.cpu_count(logical=True)}",
            f"Memory Total: {psutil.virtual_memory().total / (1024**3):.2f} GB",
            f"Memory Available: {psutil.virtual_memory().available / (1024**3):.2f} GB",
            f"Disk Usage: {psutil.disk_usage('/').percent}%"
        ]
        return "\n".join(info)
    except ImportError:
        return "psutil not installed. Basic info: " + platform.platform()
    except Exception as e:
        return f"Error fetching system info: {str(e)}"
