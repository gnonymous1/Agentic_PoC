import subprocess
import sys
import os
from langchain_core.tools import tool
from typing import Annotated

@tool
def install_package(package_name: Annotated[str, "The name of the python package to install (pip)"]) -> str:
    """
    Installs a python package using pip.
    """
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return f"Successfully installed {package_name}"
    except subprocess.CalledProcessError as e:
        return f"Failed to install {package_name}. Error: {e}"

@tool
def restart_system() -> str:
    """
    Restarts the current python process. 
    Use this after installing new packages or modifying core code to apply changes.
    """
    print("[System] Restarting...")
    os.execv(sys.executable, ['python'] + sys.argv)
    return "Restarting system..."
