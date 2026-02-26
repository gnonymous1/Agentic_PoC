from langchain_core.tools import tool
from typing import Annotated
import subprocess

@tool
def ping_host(host: Annotated[str, "Host to ping"]) -> str:
    """Pings a remote host to check connectivity."""
    try:
        cmd = ["ping", "-c", "4", host]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"Ping failed: {str(e)}"

@tool
def curl_request(url: Annotated[str, "URL to request"], method: str = "GET") -> str:
    """Makes a raw HTTP request using curl."""
    try:
        cmd = ["curl", "-X", method, "-L", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout[:2000] + ("\n...[truncated]" if len(result.stdout) > 2000 else "")
    except Exception as e:
        return f"Curl failed: {str(e)}"
