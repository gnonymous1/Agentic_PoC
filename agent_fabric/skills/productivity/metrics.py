from langchain_core.tools import tool
from typing import Annotated

@tool
def calculate_efficiency(task_log: Annotated[str, "Log of tasks completed"]) -> str:
    """Calculates productivity metrics from a log."""
    return "Productivity Score: 85% (Simulated)"
