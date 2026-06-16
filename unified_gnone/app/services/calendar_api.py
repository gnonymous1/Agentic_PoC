"""
GNONE — Calendar API Integration Service.
Google Calendar and Microsoft Graph for meeting scheduling and polling.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


async def poll_google_calendar(access_token: str, time_min: Optional[str] = None, time_max: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch upcoming events from Google Calendar API."""
    logger.info("CalendarAPI: Polling Google Calendar")

    params = {"singleEvents": "true", "orderBy": "startTime"}
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    events = []
    for item in data.get("items", []):
        events.append({
            "id": item["id"],
            "summary": item.get("summary", "No title"),
            "start": item["start"].get("dateTime", item["start"].get("date")),
            "attendees": [a.get("email") for a in item.get("attendees", [])],
            "conference": item.get("conferenceData", {}).get("entryPoints", []),
        })

    return events


async def poll_microsoft_graph(access_token: str) -> List[Dict[str, Any]]:
    """Fetch upcoming events from Microsoft Graph (Outlook Calendar)."""
    logger.info("CalendarAPI: Polling Microsoft Graph")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me/calendarview",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"startDateTime": datetime.utcnow().isoformat(), "endDateTime": datetime.utcnow().replace(hour=23, minute=59).isoformat()},
        )
        resp.raise_for_status()
        data = resp.json()

    events = []
    for item in data.get("value", []):
        events.append({
            "id": item["id"],
            "summary": item.get("subject", "No title"),
            "start": item.get("start", {}).get("dateTime"),
            "attendees": [a.get("emailAddress", {}).get("address") for a in item.get("attendees", [])],
            "online_meeting": item.get("onlineMeeting", {}).get("joinUrl"),
        })

    return events


async def create_calendar_event(access_token: str, title: str, attendees: List[str], duration_min: int = 30, provider: str = "google") -> Dict[str, Any]:
    """Create a calendar event."""
    from datetime import timedelta

    start = datetime.utcnow()
    end = start + timedelta(minutes=duration_min)

    if provider == "google":
        event_body = {
            "summary": title,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "attendees": [{"email": a} for a in attendees],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=event_body,
            )
            resp.raise_for_status()
            return {"status": "success", "event": resp.json()}
    else:
        event_body = {
            "subject": title,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
            "attendees": [{"emailAddress": {"address": a}} for a in attendees],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/me/events",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=event_body,
            )
            resp.raise_for_status()
            return {"status": "success", "event": resp.json()}
