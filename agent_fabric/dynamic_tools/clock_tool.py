import os
from datetime import datetime

def get_current_time(timezone: str = "UTC") -> str:
    """Returns the current time in the specified timezone."""
    # Simplified mock implementation
    now = datetime.now()
    return f"The current {timezone} time is {now.strftime('%H:%M:%S')}"

# Metadata for ToolLoader
name = "get_current_time"
description = "Get the current time in a given timezone (default UTC)"
