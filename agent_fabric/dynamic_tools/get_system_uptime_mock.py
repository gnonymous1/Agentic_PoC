from langchain_core.tools import tool
@tool
def get_system_uptime_mock() -> str:
    """Returns a mock system uptime."""
    return "System uptime: 124 minutes (Mock)"