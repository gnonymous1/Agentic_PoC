"""
Dashboard route — serves the browser-based interactive SEPE control panel.
Root URL redirects here for the full GUI experience.
"""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Dashboard"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    html_path = os.path.join(
        os.path.dirname(__file__), "..", "templates", "dashboard.html"
    )
    html_path = os.path.normpath(html_path)
    try:
        with open(html_path, encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        logger.warning("Dashboard template not found at %s", html_path)
        return HTMLResponse(
            content="<h1>SEPE Dashboard</h1><p>Template not found. Run with `python simulate_all.py` for CLI mode.</p>"
        )
