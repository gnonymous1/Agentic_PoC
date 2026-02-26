@echo off
echo Starting Agentic AI CLI (Venv Mode)...
cd /d "%~dp0"

if not exist venv (
    echo Virtual environment not found! Please run run_dashboard.bat first to set it up.
    pause
    exit
)

venv\Scripts\python main.py
pause
