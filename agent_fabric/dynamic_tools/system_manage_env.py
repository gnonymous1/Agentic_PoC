from langchain_core.tools import tool
import os

@tool
def system_manage_env(action: str, var_name: str, value: str = None) -> str:
    """
    Manage environment variables. Can set or get environment variables.
    
    Args:
        action: Either 'set' or 'get'
        var_name: Name of the environment variable
        value: Value to set (only needed for 'set' action)
    
    Returns:
        For 'get': the value of the environment variable or empty string if not set
        For 'set': confirmation message
    """
    if action == 'set':
        if value is None:
            return "Error: value parameter required for set action"
        os.environ[var_name] = value
        return f"Set {var_name}={value}"
    elif action == 'get':
        return os.environ.get(var_name, '')
    else:
        return f"Error: Unknown action '{action}'. Use 'set' or 'get'."