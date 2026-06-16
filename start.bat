@echo off
title GNONE — SEPE Platform
setlocal enabledelayedexpansion

echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║     SEPE — SOVEREIGN EXECUTIVE PROXY ENGINE                    ║
echo  ║     Starting Frontend + Backend                                ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
echo  Backend  : http://localhost:8000
echo  Frontend : http://localhost:3000
echo  API Docs : http://localhost:8000/docs
echo.

echo  [v] Initializing backend (uvicorn on port 8000) ...
start "SEPE-Backend" /B python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo  [v] Initializing frontend (Streamlit on port 3000) ...
start "SEPE-Frontend" /B streamlit run streamlit_app.py --server.port 3000 --server.headless true

echo.
echo  Backend LIVE  — PID: (see uvicorn output above)
echo  Frontend LIVE — PID: (see streamlit output above)
echo.
echo  Backend  : http://localhost:8000
echo  Frontend : http://localhost:3000
echo  API Docs : http://localhost:8000/docs
echo.

:wait
timeout /t 86400 /nobreak >nul 2>&1
