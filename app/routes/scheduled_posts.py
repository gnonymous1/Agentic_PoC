import logging
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from database.connection import get_session
from database.models import ScheduledPost

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scheduled", tags=["ScheduledPosts"])


class ScheduledPostRequest(BaseModel):
    client_id: str
    platform: str
    content: dict
    scheduled_at: datetime
    agent_profile_id: str | None = None


@router.post("/create")
async def create_scheduled_post(req: ScheduledPostRequest):
    db_session = await anext(get_session())
    sp = ScheduledPost(
        client_id=req.client_id,
        platform=req.platform,
        content=req.content,
        scheduled_at=req.scheduled_at,
        agent_profile_id=req.agent_profile_id,
    )
    db_session.add(sp)
    await db_session.flush()
    return {"id": str(sp.id), "status": sp.status}


@router.get("/list")
async def list_scheduled_posts(client_id: str):
    from uuid import UUID

    from sqlalchemy import select
    db_session = await anext(get_session())
    try:
        client_uuid = UUID(client_id)
    except (ValueError, TypeError):
        client_uuid = client_id
    rows = await db_session.execute(select(ScheduledPost).where(ScheduledPost.client_id == client_uuid))
    posts = rows.scalars().all()
    return [
        {"id": str(p.id), "platform": p.platform, "scheduled_at": p.scheduled_at.isoformat(), "status": p.status}
        for p in posts
    ]
