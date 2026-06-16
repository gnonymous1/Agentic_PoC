@echo off
title SEPE — Sovereign Executive Proxy Engine
setlocal enabledelayedexpansion

:menu
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║     SEPE — SOVEREIGN EXECUTIVE PROXY ENGINE                    ║
echo  ║     Launch Control Panel                                       ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  [1] Start Full Project    (port 8080 — pre-flight check + launch)
echo  [2] Run Interactive CLI Demo  (python simulate_all.py)
echo  [3] Launch Streamlit UI       (streamlit run streamlit_app.py)
echo  [4] Run All Tests             (pytest --tb=short)
echo  [5] Open E2E Tests Only       (pytest tests/e2e/ -v --tb=short)
echo  [6] Exit
echo.

set /p choice="  Select option [1-6]: "

if "%choice%"=="1" goto start_full
if "%choice%"=="2" goto cli_demo
if "%choice%"=="3" goto streamlit
if "%choice%"=="4" goto all_tests
if "%choice%"=="5" goto e2e_tests
if "%choice%"=="6" goto exit
echo  Invalid option. Please select 1-6.
timeout /t 2 /nobreak >nul
goto menu

:: ── Option 1: Pre-flight check + launch ────────────────────────────
:start_full
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║              SEPE — Pre-Flight Verification                     ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.

set ALL_PASSED=1

if not exist ".env" (
    echo  [X] .env file missing — create one with: OPENROUTER_API_KEY=sk-or-...
    set ALL_PASSED=0
) else (
    echo  [v] .env file found
    findstr /B "OPENROUTER_API_KEY=sk-or" .env >nul 2>&1
    if errorlevel 1 (
        echo  [X] OPENROUTER_API_KEY missing or invalid format in .env
        set ALL_PASSED=0
    ) else (
        echo  [v] OPENROUTER_API_KEY set (sk-or-...)
    )
)

if not exist "app\templates\dashboard.html" (
    echo  [X] app/templates/dashboard.html missing
    set ALL_PASSED=0
) else (
    echo  [v] Dashboard template found
)

python -c "import fastapi, uvicorn, httpx, pydantic, pydantic_settings; print('ok')" >nul 2>&1
if errorlevel 1 (
    echo  [X] Core dependencies missing — run: pip install -r requirements.txt
    set ALL_PASSED=0
) else (
    echo  [v] Core Python dependencies installed
)

python -c "import app.main; print('ok')" >nul 2>&1
if errorlevel 1 (
    echo  [X] app.main module failed — check for syntax errors
    set ALL_PASSED=0
) else (
    echo  [v] Application module imports cleanly
)

netstat -an 2>nul | findstr ":8080 " >nul
if not errorlevel 1 (
    echo  [X] Port 8080 is already in use — close the other process first
    set ALL_PASSED=0
) else (
    echo  [v] Port 8080 is available
)

echo.
echo  ────────────────────────────────────────────────────────────
echo   Models:
echo     Generator : deepseek/deepseek-v4-flash:free
echo     Fallback 1: nousresearch/hermes-3-llama-3.1-405b:free
echo     Fallback 2: poolside/laguna-m.1:free
echo     Fallback 3: baidu/cobuddy:free
echo     Critic    : nvidia/nemotron-3-super-120b-a12b:free
echo  ────────────────────────────────────────────────────────────
echo   Mode: Simulation (default) — toggle to LIVE in dashboard
echo   Live endpoints: /api/v1/live/* (status, manufacture, clone-chat,
echo   zoom-session, voice-clone, hitl, deploy)
echo   Requires configured API keys for live LLM calls
echo  ────────────────────────────────────────────────────────────
echo.

if !ALL_PASSED!==0 (
    echo  Some checks failed. Aborting.
    pause
    goto menu
)

echo  All checks passed. Starting server...
echo.
echo  ============================================================
echo   Dashboard : http://localhost:8080
echo   API Docs  : http://localhost:8080/docs
echo   Simulation: Open Dashboard ^> Simulation tab
echo   Press Ctrl+C to stop.
echo  ============================================================
echo.
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
echo.
pause
goto menu

:: ── Option 2: CLI Demo ────────────────────────────────────────────
:cli_demo
cls
echo.
echo  Starting interactive CLI simulation...
echo.
python simulate_all.py
echo.
pause
goto menu

:: ── Option 3: Streamlit UI ─────────────────────────────────────────
:streamlit
cls
echo.
echo  Starting Streamlit content studio on http://localhost:8501 ...
echo.
streamlit run streamlit_app.py --server.port 8501
echo.
pause
goto menu

:: ── Option 4: All Tests ────────────────────────────────────────────
:all_tests
cls
echo.
echo  Running full test suite...
echo.
python -m pytest --tb=short -v
echo.
pause
goto menu

:: ── Option 5: E2E Tests Only ───────────────────────────────────────
:e2e_tests
cls
echo.
echo  Running E2E tests...
echo.
python -m pytest tests/e2e/ -v --tb=short
echo.
pause
goto menu

:: ── Exit ───────────────────────────────────────────────────────────
:exit
echo.
echo  Exiting. Goodbye.
timeout /t 1 /nobreak >nul
exit /b 0
