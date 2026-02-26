import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import webbrowser
import time
import threading

# Configuration
VENV_PYTHON = os.path.join("venv", "Scripts", "python.exe")
SERVER_CMD = [VENV_PYTHON, "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
DASHBOARD_URL = "http://localhost:8000/dashboard"

class ServerLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Agentic AI Control Panel")
        self.root.geometry("350x250")
        self.root.resizable(False, False)
        
        self.server_process = None
        self.is_running = False

        # Status Label
        self.status_label = tk.Label(root, text="Status: Stopped", fg="red", font=("Arial", 14, "bold"))
        self.status_label.pack(pady=20)

        # Buttons Frame
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        # Start Button
        self.btn_start = tk.Button(btn_frame, text="Start Server", command=self.start_server, bg="#4CAF50", fg="white", font=("Arial", 12), width=12)
        self.btn_start.grid(row=0, column=0, padx=10)

        # Stop Button
        self.btn_stop = tk.Button(btn_frame, text="Stop Server", command=self.stop_server, bg="#F44336", fg="white", font=("Arial", 12), width=12, state=tk.DISABLED)
        self.btn_stop.grid(row=0, column=1, padx=10)

        # Dashboard Button
        self.btn_dash = tk.Button(root, text="Open Dashboard", command=self.open_dashboard, bg="#2196F3", fg="white", font=("Arial", 11), width=20)
        self.btn_dash.pack(pady=20)

        # Handle Close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_server(self):
        if self.is_running:
            return
        
        try:
            # Check if virtual environment exists
            if not os.path.exists(VENV_PYTHON):
                messagebox.showerror("Error", "Virtual Environment not found.\nPlease run 'run_dashboard.bat' once to set it up.")
                return

            # Start Process
            # Creationflags=subprocess.CREATE_NEW_CONSOLE ensures it runs in a separate window (or background if desired)
            # For this GUI, let's keep it hidden or minimized? User asked for buttons.
            # Let's run it without console window for cleaner experience, but capture output?
            # Or simpler: run with CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.server_process = subprocess.Popen(
                SERVER_CMD,
                cwd=os.getcwd(),
                # stdout=subprocess.PIPE, 
                # stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE 
            )
            
            self.is_running = True
            self.update_ui_state()
            
            # Auto-open dashboard after a few seconds
            threading.Thread(target=self.delayed_open_dashboard).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {e}")

    def stop_server(self):
        if not self.is_running or not self.server_process:
            return

        try:
            # Hard kill for PoC
            # self.server_process.terminate() 
            # On Windows terminate might not kill the tree (uvicorn -> python). 
            # Using taskkill is often more reliable for detached processes.
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.server_process.pid)])
            
            self.server_process = None
            self.is_running = False
            self.update_ui_state()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop server: {e}")

    def delayed_open_dashboard(self):
        time.sleep(3)
        self.open_dashboard()

    def open_dashboard(self):
        webbrowser.open(DASHBOARD_URL)

    def update_ui_state(self):
        if self.is_running:
            self.status_label.config(text="Status: Running", fg="green")
            self.btn_start.config(state=tk.DISABLED, bg="#a5d6a7") # Dimmed
            self.btn_stop.config(state=tk.NORMAL, bg="#F44336")
        else:
            self.status_label.config(text="Status: Stopped", fg="red")
            self.btn_start.config(state=tk.NORMAL, bg="#4CAF50")
            self.btn_stop.config(state=tk.DISABLED, bg="#ef9a9a") # Dimmed

    def on_close(self):
        if self.is_running:
            if messagebox.askokcancel("Quit", "Server is running. Stop it and quit?"):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    # Ensure dependencies are installed? We assume so from venv.
    root = tk.Tk()
    app = ServerLauncher(root)
    root.mainloop()
