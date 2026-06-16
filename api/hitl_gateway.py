"""
Human-in-the-Loop (HITL) workflow gateway.
Provides FastAPI endpoints for approve/reject/rewrite state transitions
on automated clone actions.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_session
from database.models import HitlAction
from services.critic import HITLStateMachine, rewrite_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hitl", tags=["Human-in-the-Loop"])


class HitlActionRequest(BaseModel):
    action_id: str = Field(..., description="UUID of the HITL action")
    notes: str = Field("", description="Reason or feedback for the transition")


class HitlActionResponse(BaseModel):
    status: str
    action_id: str
    previous_status: str
    message: str


class HitlRewriteRequest(BaseModel):
    action_id: str = Field(..., description="UUID of the HITL action to rewrite")
    rewrite_notes: str = Field(..., description="Specific issues to fix in the rewrite")
    original_utd: str = Field(..., description="The original UTD used for generation")
    brand_voice: str = Field("", description="Brand voice instructions for the rewrite")


class HitlListResponse(BaseModel):
    actions: list[dict]
    total: int


@router.get("/actions", response_model=HitlListResponse)
async def list_pending_actions(
    status_filter: str = "PENDING_HUMAN_SIGN_OFF",
    client_id: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """
    List HITL actions, optionally filtered by status and client.
    """
    stmt = select(HitlAction).where(HitlAction.status == status_filter)
    if client_id:
        stmt = stmt.where(HitlAction.client_id == UUID(client_id))
    stmt = stmt.order_by(HitlAction.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    actions = result.scalars().all()

    return HitlListResponse(
        actions=[
            {
                "id": str(a.id),
                "client_id": str(a.client_id),
                "agent_profile_id": str(a.agent_profile_id) if a.agent_profile_id else None,
                "action_type": a.action_type,
                "status": a.status,
                "target_platform": a.target_platform,
                "payload_summary": str(a.payload)[:200] if a.payload else "",
                "refinement_notes": a.refinement_notes,
                "original_action_id": str(a.original_action_id) if a.original_action_id else None,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ],
        total=len(actions),
    )


@router.post("/approve", response_model=HitlActionResponse)
async def approve_action(
    req: HitlActionRequest,
    session: AsyncSession = Depends(get_session),
):
    """APPROVE a pending HITL action for deployment."""
    try:
        stmt = select(HitlAction).where(HitlAction.id == UUID(req.action_id))
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid action_id: {exc}")

    if not action:
        raise HTTPException(status_code=404, detail=f"HITL action not found: {req.action_id}")

    previous_status = action.status

    try:
        await HITLStateMachine.approve(action, db_session=session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await session.commit()

    return HitlActionResponse(
        status="APPROVED",
        action_id=req.action_id,
        previous_status=previous_status,
        message="Action approved. Route to /api/v1/hitl/deploy to deploy.",
    )


@router.post("/reject", response_model=HitlActionResponse)
async def reject_action(
    req: HitlActionRequest,
    session: AsyncSession = Depends(get_session),
):
    """REJECT a pending HITL action — purges it from the queue."""
    try:
        stmt = select(HitlAction).where(HitlAction.id == UUID(req.action_id))
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid action_id: {exc}")

    if not action:
        raise HTTPException(status_code=404, detail=f"HITL action not found: {req.action_id}")

    previous_status = action.status

    try:
        await HITLStateMachine.reject(action, reason=req.notes, db_session=session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await session.commit()

    return HitlActionResponse(
        status="REJECTED",
        action_id=req.action_id,
        previous_status=previous_status,
        message="Action rejected and purged from queue.",
    )


@router.post("/rewrite", response_model=HitlActionResponse)
async def force_rewrite(
    req: HitlRewriteRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    FORCE_REWRITE a pending HITL action.
    Extracts error context and routes back to generator for auto-healed rewrite.
    """
    try:
        stmt = select(HitlAction).where(HitlAction.id == UUID(req.action_id))
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid action_id: {exc}")

    if not action:
        raise HTTPException(status_code=404, detail=f"HITL action not found: {req.action_id}")

    previous_status = action.status

    try:
        result = await rewrite_action(
            action=action,
            rewrite_notes=req.rewrite_notes,
            original_utd=req.original_utd,
            brand_voice=req.brand_voice or None,
            db_session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        logger.error("Rewrite failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rewrite failed: {str(exc)[:300]}")

    await session.commit()

    return HitlActionResponse(
        status=result.get("status", "REWRITE_COMPLETED"),
        action_id=req.action_id,
        previous_status=previous_status,
        message=f"Rewrite completed. Replacement action: {result.get('replacement_action_id', 'N/A')}",
    )


@router.post("/deploy", response_model=HitlActionResponse)
async def deploy_action(
    req: HitlActionRequest,
    session: AsyncSession = Depends(get_session),
):
    """DEPLOY an approved HITL action to its target platform."""
    try:
        stmt = select(HitlAction).where(HitlAction.id == UUID(req.action_id))
        result = await session.execute(stmt)
        action = result.scalar_one_or_none()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid action_id: {exc}")

    if not action:
        raise HTTPException(status_code=404, detail=f"HITL action not found: {req.action_id}")

    if action.status != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail=f"Action must be APPROVED before deploy. Current status: {action.status}",
        )

    previous_status = action.status

    deploy_response = {"deployed": True, "platform": action.target_platform}

    try:
        await HITLStateMachine.deploy(action, deploy_response=deploy_response, db_session=session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    await session.commit()

    return HitlActionResponse(
        status="DEPLOYED",
        action_id=req.action_id,
        previous_status=previous_status,
        message=f"Action deployed to {action.target_platform or 'default'}",
    )
