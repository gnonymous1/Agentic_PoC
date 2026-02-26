@echo off
echo Starting Agentic AI Control Panel...
cd /d "%~dp0"

if not exist venv (
    echo Virtual environment not found! Please run run_dashboard.bat first to set it up.
    pause
    exit
)

start "" venv\Scripts\pythonw.exe launcher.py
exit
