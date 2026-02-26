from langchain_core.tools import tool
from typing import Annotated
import subprocess
import os
import tempfile
import sys

def _execute_python_logic(code: str) -> str:
    """Core logic for Python execution (safe for reuse)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        return output if output else "Code executed with no output."
    except Exception as e:
        return f"Execution failed: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

@tool
def execute_python_code(code: Annotated[str, "Python code to execute"]) -> str:
    """Executes Python code safely."""
    return _execute_python_logic(code)

@tool
def git_clone(repo_url: Annotated[str, "Git repository URL"], target_dir: Annotated[str, "Target directory"] = None) -> str:
    """Clones a git repository."""
    try:
        cmd = ["git", "clone", repo_url]
        if target_dir:
            cmd.append(target_dir)

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return f"Successfully cloned {repo_url}"
        return f"Git clone failed: {result.stderr}"
    except Exception as e:
        return f"Error executing git: {str(e)}"
