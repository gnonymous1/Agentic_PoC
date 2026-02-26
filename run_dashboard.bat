@echo off
echo Starting Agentic AI Dashboard (Venv Mode)...

cd /d "%~dp0"

if not exist venv (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    echo Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
    echo Installing Playwright browsers...
    venv\Scripts\playwright install chromium
)

echo Launching Server...
start "" "http://localhost:8000/dashboard"
venv\Scripts\python -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload
pause
