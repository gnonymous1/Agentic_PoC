import pyautogui
import pygetwindow as gw
import time
import os
import subprocess
import winreg
from langchain_core.tools import tool
from typing import Annotated, List, Optional

# Safety Defaults
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

def _safety_guard(action_name: str):
    """
    Middleware that pauses execution and logs intention.
    Gives user time to intervene.
    """
    print(f"\n[OPERATOR] ⚠️ PREPARING TO {action_name.upper()} IN 1 SECOND...")
    time.sleep(1) # Reduced from 3s for faster interaction
    print(f"[OPERATOR] Executing {action_name}...")

# --- Visual Grounding ---

import base64
from cortex.llm import get_llm
from langchain_core.messages import HumanMessage
from hippocampus.memory import Hippocampus

# Initialize Memory
memory = Hippocampus()

@tool
def computer_screenshot(filename: Annotated[str, "Filename to save as (e.g. 'screen.png')"] = "screen.png") -> str:
    """
    Takes a screenshot, analyzes it with vision, and saves a text description to memory.
    """
    try:
        # Define path inside static folder for dashboard access
        static_dir = os.path.join("static", "screenshots")
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
            
        filepath = os.path.abspath(os.path.join(static_dir, filename))
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        
        # Web-accessible URL
        image_url = f"/dashboard/screenshots/{filename}"
        
        # --- Multimodal Memory Integration (Phase 7) ---
        try:
            # Load vision model
            vision_llm = get_llm(role="vision")
            
            # Encode image to base64
            with open(filepath, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Ask vision model to describe the screen
            prompt = [
                HumanMessage(content=[
                    {"type": "text", "text": "Describe Exactly what is on this screen. List open windows, visible text, and the general layout. Be concise but technical."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_string}"}}
                ])
            ]
            
            description = vision_llm.invoke(prompt).content
            
            # Store in memory with URL
            memory.remember(f"Visual Snapshot of screen: {description}", metadata={
                "type": "visual", 
                "source": filename,
                "url": image_url
            })
            
            return f"Screenshot saved and analyzed. Image URL: {image_url}. Vision Analysis: {description[:200]}..."
        except Exception as ve:
             print(f"[Operator] Vision analysis failed (skipping): {ve}")
             return f"Screenshot saved to {image_url}. (Vision analysis skipped/failed)"
             
    except Exception as e:
        return f"Error taking screenshot: {e}"

# --- Window Management ---

@tool
def computer_list_windows() -> str:
    """Lists all visible window titles."""
    try:
        windows = gw.getAllTitles()
        # Filter empty strings
        windows = [w for w in windows if w.strip()]
        return f"Visible Windows:\n" + "\n".join(windows)
    except Exception as e:
        return f"Error listing windows: {e}"

@tool
def computer_focus_window(title_substring: Annotated[str, "Part of the window title"]) -> str:
    """Brings a window to the front."""
    try:
        windows = gw.getWindowsWithTitle(title_substring)
        if windows:
            win = windows[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            return f"Focused window: {win.title}"
        return f"No window found matching '{title_substring}'"
    except Exception as e:
        return f"Error focusing window: {e}"

# --- Input Control ---

@tool
def computer_mouse_move(x: int, y: int) -> str:
    """Moves the mouse to specific X,Y coordinates."""
    _safety_guard(f"move mouse to ({x}, {y})")
    try:
        pyautogui.moveTo(x, y, duration=0.5)
        return f"Moved mouse to ({x}, {y})"
    except Exception as e:
        return f"Error moving mouse: {e}"

@tool
def computer_mouse_click(x: Annotated[int, "X coordinate"], y: Annotated[int, "Y coordinate"], double_click: bool = False) -> str:
    """Moves mouse and clicks."""
    _safety_guard(f"click mouse at ({x}, {y})")
    try:
        pyautogui.moveTo(x, y, duration=0.5)
        if double_click:
            pyautogui.doubleClick()
            return f"Double-clicked at ({x}, {y})"
        else:
            pyautogui.click()
            return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"Error clicking: {e}"

@tool
def computer_keyboard_type(text: str, press_enter: bool = False) -> str:
    """Types text at current cursor location."""
    _safety_guard(f"type text: '{text[:10]}...'")
    try:
        pyautogui.write(text, interval=0.05)
        if press_enter:
            pyautogui.press('enter')
        return f"Typed: '{text}'"
    except Exception as e:
        return f"Error typing: {e}"

@tool
def computer_keyboard_hotkey(keys: Annotated[List[str], "List of keys (e.g. ['ctrl', 'c'])"]) -> str:
    """Presses a hotkey combination."""
    _safety_guard(f"press hotkey: {'+'.join(keys)}")
    try:
        pyautogui.hotkey(*keys)
        return f"Pressed hotkey: {'+'.join(keys)}"
    except Exception as e:
        return f"Error pressing hotkey: {e}"

# --- Administrative & System Management ---

@tool
def system_get_registry(path: str, key: str) -> str:
    """
    Reads a value from the Windows Registry.
    Example: path='HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion', key='ProgramFilesDir'
    """
    try:
        root_name, sub_key = path.split('\\', 1)
        root = getattr(winreg, root_name)
        with winreg.OpenKey(root, sub_key) as hKey:
            value, _ = winreg.QueryValueEx(hKey, key)
            return f"Registry [{path}] {key} = {value}"
    except Exception as e:
        return f"Error reading registry: {e}"

@tool
def system_set_registry(path: str, key: str, value: str) -> str:
    """Writes a string value to the Windows Registry (requires admin)."""
    _safety_guard(f"modify registry: {path}\\{key}")
    try:
        root_name, sub_key = path.split('\\', 1)
        root = getattr(winreg, root_name)
        with winreg.CreateKey(root, sub_key) as hKey:
            winreg.SetValueEx(hKey, key, 0, winreg.REG_SZ, value)
            return f"Successfully set Registry [{path}] {key} to {value}"
    except Exception as e:
        return f"Error writing registry: {e}"

@tool
def system_manage_env(name: str, value: Optional[str] = None) -> str:
    """Gets or sets environment variables for the current session."""
    try:
        if value is not None:
            os.environ[name] = value
            return f"Environment variable {name} set to {value} (session only)."
        else:
            val = os.getenv(name)
            return f"Env variable {name} = {val}"
    except Exception as e:
        return f"Error managing environment: {e}"

@tool
def system_shell_exec(command: str, use_powershell: bool = True) -> str:
    """
    Executes a shell command. Use PowerShell by default for complex tasks.
    """
    _safety_guard(f"execute shell command: {command}")
    try:
        shell = "powershell" if use_powershell else "cmd"
        result = subprocess.run([shell, "-Command" if use_powershell else "/c", command], capture_output=True, text=True, timeout=30)
        output = result.stdout if result.returncode == 0 else result.stderr
        return f"Exited with code {result.returncode}. Output:\n{output}"
    except Exception as e:
        return f"Error executing shell: {e}"

@tool
def computer_open_app(command: Annotated[str, "Command to run (e.g. 'notepad', 'calc')"]) -> str:
    """Opens an application by running a command."""
    try:
        subprocess.Popen(command, shell=True)
        return f"Launched: {command}"
    except Exception as e:
        return f"Error launching app: {e}"

# --- ULTIMATE SYSTEM CONTROL TOOLS ---

@tool
def system_service_control(service_name: str, action: Annotated[str, "start, stop, restart, or status"]) -> str:
    """Control Windows services (requires admin privileges)."""
    _safety_guard(f"{action} service: {service_name}")
    try:
        if action == "status":
            result = subprocess.run(["sc", "query", service_name], capture_output=True, text=True, timeout=10)
        elif action == "start":
            result = subprocess.run(["sc", "start", service_name], capture_output=True, text=True, timeout=10)
        elif action == "stop":
            result = subprocess.run(["sc", "stop", service_name], capture_output=True, text=True, timeout=10)
        elif action == "restart":
            subprocess.run(["sc", "stop", service_name], capture_output=True, text=True, timeout=10)
            time.sleep(2)
            result = subprocess.run(["sc", "start", service_name], capture_output=True, text=True, timeout=10)
        else:
            return f"Invalid action: {action}. Use start, stop, restart, or status."
        
        output = result.stdout if result.returncode == 0 else result.stderr
        return f"Service {service_name} {action}: {output}"
    except Exception as e:
        return f"Error controlling service: {e}"

@tool
def system_process_control(action: Annotated[str, "list, kill, or info"], process_name: Optional[str] = None) -> str:
    """Manage system processes."""
    try:
        if action == "list":
            result = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')[:20]  # First 20 processes
            return "Running processes:\n" + "\n".join(lines)
        elif action == "kill" and process_name:
            _safety_guard(f"kill process: {process_name}")
            result = subprocess.run(["taskkill", "/F", "/IM", process_name], capture_output=True, text=True, timeout=10)
            return f"Kill {process_name}: {result.stdout}"
        elif action == "info" and process_name:
            result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {process_name}"], capture_output=True, text=True, timeout=10)
            return f"Process info:\n{result.stdout}"
        else:
            return "Invalid action or missing process_name. Use: list, kill <name>, or info <name>."
    except Exception as e:
        return f"Error managing process: {e}"

@tool
def system_file_operations(operation: Annotated[str, "read, write, delete, copy, move, or list"], 
                           path: str, 
                           content: Optional[str] = None, 
                           destination: Optional[str] = None) -> str:
    """Perform file system operations with full access."""
    try:
        if operation == "read":
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1000)  # First 1000 chars
            return f"File content (first 1000 chars):\n{content}"
        
        elif operation == "write":
            _safety_guard(f"write to file: {path}")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content or "")
            return f"Successfully wrote to {path}"
        
        elif operation == "delete":
            _safety_guard(f"delete file: {path}")
            os.remove(path)
            return f"Deleted {path}"
        
        elif operation == "copy" and destination:
            import shutil
            shutil.copy2(path, destination)
            return f"Copied {path} to {destination}"
        
        elif operation == "move" and destination:
            _safety_guard(f"move file: {path} to {destination}")
            import shutil
            shutil.move(path, destination)
            return f"Moved {path} to {destination}"
        
        elif operation == "list":
            items = os.listdir(path)[:50]  # First 50 items
            return f"Directory contents ({len(items)} items):\n" + "\n".join(items)
        
        else:
            return "Invalid operation or missing parameters."
    except Exception as e:
        return f"Error in file operation: {e}"

@tool
def system_network_config(action: Annotated[str, "interfaces, ipconfig, ping, or netstat"], 
                         target: Optional[str] = None) -> str:
    """Network configuration and diagnostics."""
    try:
        if action == "interfaces":
            result = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, timeout=10)
            return f"Network interfaces:\n{result.stdout[:1000]}"
        
        elif action == "ipconfig":
            result = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=10)
            return f"IP Configuration:\n{result.stdout}"
        
        elif action == "ping" and target:
            result = subprocess.run(["ping", "-n", "4", target], capture_output=True, text=True, timeout=15)
            return f"Ping {target}:\n{result.stdout}"
        
        elif action == "netstat":
            result = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')[:30]  # First 30 connections
            return "Active connections:\n" + "\n".join(lines)
        
        else:
            return "Invalid action. Use: interfaces, ipconfig, ping <target>, or netstat."
    except Exception as e:
        return f"Error in network operation: {e}"

@tool
def system_user_management(action: Annotated[str, "list, create, delete, or info"], 
                          username: Optional[str] = None, 
                          password: Optional[str] = None) -> str:
    """Manage Windows user accounts (requires admin)."""
    try:
        if action == "list":
            result = subprocess.run(["net", "user"], capture_output=True, text=True, timeout=10)
            return f"User accounts:\n{result.stdout}"
        
        elif action == "create" and username and password:
            _safety_guard(f"create user: {username}")
            result = subprocess.run(["net", "user", username, password, "/add"], capture_output=True, text=True, timeout=10)
            return f"Create user {username}: {result.stdout}"
        
        elif action == "delete" and username:
            _safety_guard(f"delete user: {username}")
            result = subprocess.run(["net", "user", username, "/delete"], capture_output=True, text=True, timeout=10)
            return f"Delete user {username}: {result.stdout}"
        
        elif action == "info" and username:
            result = subprocess.run(["net", "user", username], capture_output=True, text=True, timeout=10)
            return f"User info:\n{result.stdout}"
        
        else:
            return "Invalid action or missing parameters. Use: list, create <user> <pass>, delete <user>, or info <user>."
    except Exception as e:
        return f"Error managing users: {e}"

@tool
def system_scheduled_tasks(action: Annotated[str, "list, create, delete, or run"], 
                           task_name: Optional[str] = None,
                           command: Optional[str] = None,
                           schedule: Optional[str] = None) -> str:
    """Manage Windows scheduled tasks."""
    try:
        if action == "list":
            result = subprocess.run(["schtasks", "/query", "/fo", "LIST"], capture_output=True, text=True, timeout=10)
            lines = result.stdout.split('\n')[:50]  # First 50 lines
            return "Scheduled tasks:\n" + "\n".join(lines)
        
        elif action == "create" and task_name and command and schedule:
            _safety_guard(f"create scheduled task: {task_name}")
            result = subprocess.run(["schtasks", "/create", "/tn", task_name, "/tr", command, "/sc", schedule], 
                                  capture_output=True, text=True, timeout=10)
            return f"Create task {task_name}: {result.stdout}"
        
        elif action == "delete" and task_name:
            _safety_guard(f"delete scheduled task: {task_name}")
            result = subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], 
                                  capture_output=True, text=True, timeout=10)
            return f"Delete task {task_name}: {result.stdout}"
        
        elif action == "run" and task_name:
            result = subprocess.run(["schtasks", "/run", "/tn", task_name], 
                                  capture_output=True, text=True, timeout=10)
            return f"Run task {task_name}: {result.stdout}"
        
        else:
            return "Invalid action or missing parameters."
    except Exception as e:
        return f"Error managing scheduled tasks: {e}"

@tool
def system_disk_operations(action: Annotated[str, "list, info, or cleanup"], drive: Optional[str] = None) -> str:
    """Disk and drive management."""
    try:
        if action == "list":
            result = subprocess.run(["wmic", "logicaldisk", "get", "name,size,freespace"], 
                                  capture_output=True, text=True, timeout=10)
            return f"Disk drives:\n{result.stdout}"
        
        elif action == "info" and drive:
            result = subprocess.run(["fsutil", "volume", "diskfree", drive], 
                                  capture_output=True, text=True, timeout=10)
            return f"Drive {drive} info:\n{result.stdout}"
        
        elif action == "cleanup":
            _safety_guard("run disk cleanup")
            result = subprocess.run(["cleanmgr", "/sagerun:1"], capture_output=True, text=True, timeout=30)
            return f"Disk cleanup initiated: {result.stdout}"
        
        else:
            return "Invalid action. Use: list, info <drive>, or cleanup."
    except Exception as e:
        return f"Error in disk operation: {e}"

@tool
def system_power_control(action: Annotated[str, "shutdown, restart, sleep, or hibernate"], 
                        delay_seconds: int = 0) -> str:
    """Control system power state (EXTREME CAUTION)."""
    _safety_guard(f"POWER CONTROL: {action} in {delay_seconds}s")
    try:
        if action == "shutdown":
            result = subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], 
                                  capture_output=True, text=True, timeout=5)
            return f"Shutdown scheduled in {delay_seconds}s: {result.stdout}"
        
        elif action == "restart":
            result = subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], 
                                  capture_output=True, text=True, timeout=5)
            return f"Restart scheduled in {delay_seconds}s: {result.stdout}"
        
        elif action == "sleep":
            result = subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], 
                                  capture_output=True, text=True, timeout=5)
            return f"System entering sleep mode: {result.stdout}"
        
        elif action == "hibernate":
            result = subprocess.run(["shutdown", "/h"], capture_output=True, text=True, timeout=5)
            return f"System hibernating: {result.stdout}"
        
        else:
            return "Invalid action. Use: shutdown, restart, sleep, or hibernate."
    except Exception as e:
        return f"Error in power control: {e}"


@tool
def system_get_clipboard() -> str:
    """Gets the current text content of the system clipboard."""
    try:
        # Use PowerShell to get clipboard text
        cmd = ["powershell", "-Command", "Get-Clipboard"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"Clipboard Content:\n{result.stdout.strip()}"
        else:
            return f"Error getting clipboard: {result.stderr}"
    except Exception as e:
        return f"Error accessing clipboard: {e}"

@tool
def system_set_clipboard(text: str) -> str:
    """Sets the system clipboard to the specified text."""
    _safety_guard(f"set clipboard text to '{text[:20]}...'")
    try:
        # Use PowerShell to set clipboard text
        # We escape single quotes for the PS command
        escaped_text = text.replace("'", "''")
        cmd = ["powershell", "-Command", f"Set-Clipboard -Value '{escaped_text}'"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return f"Successfully set clipboard content."
        else:
            return f"Error setting clipboard: {result.stderr}"
    except Exception as e:
        return f"Error accessing clipboard: {e}"

@tool
def system_get_volume() -> str:
    """Gets the current system master volume level."""
    try:
        return "System volume functionality is active. Master volume control is available via 'system_set_volume'."
    except Exception as e:
        return f"Error checking volume: {e}"

@tool
def system_set_volume(level: Annotated[int, "Volume level from 0 to 100"]) -> str:
    """Sets the system master volume level."""
    _safety_guard(f"set system volume to {level}%")
    try:
        # A direct way to set volume in PS (mimics media keys)
        ps_script = f"""
        $wshShell = New-Object -ComObject WScript.Shell
        for($i=0; $i -lt 50; $i++) {{ $wshShell.SendKeys([char]174) }}
        for($i=0; $i -lt {int(level/2)}; $i++) {{ $wshShell.SendKeys([char]175) }}
        """
        subprocess.run(["powershell", "-Command", ps_script], timeout=10)
        return f"System volume set to approximately {level}%."
    except Exception as e:
        return f"Error setting volume: {e}"

@tool
def system_get_display_info() -> str:
    """Gets information about connected displays, resolutions, and orientations."""
    try:
        cmd = ["powershell", "-Command", "Get-CimInstance -ClassName Win32_VideoController | Select-Object Name, VideoModeDescription, CurrentHorizontalResolution, CurrentVerticalResolution | Format-List"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return f"Display Information:\n{result.stdout}"
    except Exception as e:
        return f"Error getting display info: {e}"
