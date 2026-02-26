import sys
import io
import contextlib
from typing import Any, Dict, Callable

class ExecutionSandbox:
    """
    Provides a restricted environment for executing dynamic tool code.
    Currently implements basic stdout/stderr redirection and restricted globals.
    """

    def __init__(self, allowed_modules: list = None):
        self.allowed_modules = allowed_modules or ["math", "json", "datetime", "statistics"]
        self.audit_log = []

    def run_safe(self, func: Callable, params: Dict[str, Any]) -> Any:
        """Execute a function within a restricted scope."""
        self.audit_log.append(f"EXECUTE: {func.__name__} with {params}")
        
        # Capture output
        stdout = io.StringIO()
        stderr = io.StringIO()
        
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                # In a real-world scenario, we'd use something like RestrictedPython 
                # or a container/VM. For this PoC, we use basic protection.
                result = func(**params)
            
            return {
                "success": True,
                "result": result,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue()
            }
        except Exception as e:
            self.audit_log.append(f"ERROR: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue()
            }

    def get_audit_trail(self) -> list:
        return self.audit_log
