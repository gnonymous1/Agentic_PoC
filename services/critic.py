"""
HITL-aware critic service.
Wraps the existing asymmetric critic loop and routes outputs through the
Human-in-the-Loop approval state machine.
"""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from database.models import HitlAction
from app.models.content_models import MultiPlatformContent
from app.services.critic_loop import (
    critic_verification_loop,
    MaxRetriesExceededError,
)

logger = logging.getLogger(__name__)


class HITLStateMachine:
    """
    State-transition manager for Human-in-the-Loop actions.
    Every automated clone action flows through:
      PENDING_HUMAN_SIGN_OFF → APPROVED → DEPLOYED
                            → REJECTED → (purged)
                            → REWRITE_IN_PROGRESS → REWRITE_COMPLETED → PENDING_HUMAN_SIGN_OFF
    """

    VALID_TRANSITIONS = {
        "PENDING_HUMAN_SIGN_OFF": ["APPROVED", "REJECTED", "REWRITE_IN_PROGRESS"],
        "APPROVED": ["DEPLOYED", "FAILED"],
        "REJECTED": [],
        "REWRITE_IN_PROGRESS": ["REWRITE_COMPLETED", "FAILED"],
        "REWRITE_COMPLETED": ["PENDING_HUMAN_SIGN_OFF", "APPROVED"],
        "DEPLOYED": [],
        "FAILED": [],
    }

    @staticmethod
    def _validate_transition(current: str, target: str) -> None:
        allowed = HITLStateMachine.VALID_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise ValueError(
                f"Invalid HITL state transition: {current} → {target}. "
                f"Allowed: {allowed}"
            )

    @staticmethod
    async def approve(
        action: HitlAction,
        db_session=None,
    ) -> HitlAction:
        """APPROVE — marks action for deployment."""
        HITLStateMachine._validate_transition(action.status, "APPROVED")
        action.status = "APPROVED"
        action.approved_at = datetime.utcnow()
        if db_session:
            await db_session.flush()
        logger.info("HITL action %s APPROVED", action.id)
        return action

    @staticmethod
    async def reject(
        action: HitlAction,
        reason: str = "",
        db_session=None,
    ) -> HitlAction:
        """REJECT — purges the action from the queue."""
        HITLStateMachine._validate_transition(action.status, "REJECTED")
        action.status = "REJECTED"
        if reason:
            action.refinement_notes = reason
        if db_session:
            await db_session.flush()
        logger.info("HITL action %s REJECTED — reason=%s", action.id, reason)
        return action

    @staticmethod
    async def force_rewrite(
        action: HitlAction,
        rewrite_notes: str,
        db_session=None,
    ) -> HitlAction:
        """FORCE_REWRITE — routes back to generator for auto-healed rewrite."""
        HITLStateMachine._validate_transition(action.status, "REWRITE_IN_PROGRESS")
        action.status = "REWRITE_IN_PROGRESS"
        action.refinement_notes = rewrite_notes
        if db_session:
            await db_session.flush()
        logger.info(
            "HITL action %s → REWRITE_IN_PROGRESS — notes=%s",
            action.id, rewrite_notes[:200],
        )
        return action

    @staticmethod
    async def complete_rewrite(
        action: HitlAction,
        new_payload: dict,
        db_session=None,
    ) -> HitlAction:
        """Mark a rewrite as completed and return to PENDING_HUMAN_SIGN_OFF."""
        HITLStateMachine._validate_transition(action.status, "REWRITE_COMPLETED")
        action.status = "REWRITE_COMPLETED"
        action.payload = new_payload
        if db_session:
            await db_session.flush()
        logger.info("HITL action %s → REWRITE_COMPLETED (back to pending)", action.id)
        return action

    @staticmethod
    async def deploy(
        action: HitlAction,
        deploy_response: Optional[dict] = None,
        db_session=None,
    ) -> HitlAction:
        """DEPLOY — marks action as deployed after successful external API call."""
        HITLStateMachine._validate_transition(action.status, "DEPLOYED")
        action.status = "DEPLOYED"
        action.deployed_at = datetime.utcnow()
        action.deployed_response = deploy_response
        if db_session:
            await db_session.flush()
        logger.info("HITL action %s DEPLOYED", action.id)
        return action


async def critic_with_hitl(
    generated_content: MultiPlatformContent,
    original_utd: str,
    brand_voice: Optional[str] = None,
    agent_profile_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    db_session=None,
) -> dict:
    """
    Run the asymmetric critic loop on generated content, then record the result
    as a PENDING_HUMAN_SIGN_OFF HITL action if approved.
    """
    try:
        approved_content, cycles = await critic_verification_loop(
            generated=generated_content,
            original_utd=original_utd,
            brand_voice=brand_voice,
        )
        logger.info("Critic approved content after %d cycles", cycles)

        result = {
            "approved": True,
            "refinement_cycles": cycles,
            "content": approved_content.model_dump(),
        }

        if db_session and client_id:
            hitl_action = HitlAction(
                client_id=client_id,
                agent_profile_id=agent_profile_id,
                action_type="content_publish",
                status="PENDING_HUMAN_SIGN_OFF",
                payload=approved_content.model_dump(),
                target_platform=None,
            )
            db_session.add(hitl_action)
            await db_session.flush()
            result["hitl_action_id"] = str(hitl_action.id)
            logger.info("Content recorded as HITL action %s", hitl_action.id)

        return result

    except MaxRetriesExceededError as exc:
        logger.warning("Critic retry budget exhausted: %s", exc)
        return {
            "approved": False,
            "refinement_cycles": 3,
            "refinement_notes": exc.last_refinement_notes,
            "content": generated_content.model_dump(),
        }
    except Exception as exc:
        logger.error("Critic loop failed unexpectedly: %s", exc, exc_info=True)
        return {
            "approved": False,
            "refinement_cycles": 0,
            "refinement_notes": str(exc),
            "content": generated_content.model_dump(),
        }


async def rewrite_action(
    action: HitlAction,
    rewrite_notes: str,
    original_utd: str,
    brand_voice: Optional[str] = None,
    db_session=None,
) -> dict:
    """
    Execute a FORCE_REWRITE: extract error context, route back to the generator,
    run critic again, and produce a new HITL action referencing the original.
    """
    from services.generator import CloneGenerator
    from app.models.content_models import MultiPlatformContent

    HITLStateMachine._validate_transition(action.status, "REWRITE_IN_PROGRESS")
    action.status = "REWRITE_IN_PROGRESS"
    action.refinement_notes = rewrite_notes
    if db_session:
        await db_session.flush()

    try:
        original_content = MultiPlatformContent.model_validate(action.payload)
    except Exception:
        logger.error("Cannot parse original HITL payload for rewrite")
        action.status = "FAILED"
        if db_session:
            await db_session.flush()

        return {
            "status": "FAILED",
            "error": "Cannot parse original payload",
        }

    augmented_utd = (
        f"{original_utd}\n\n"
        f"--- CRITIC FEEDBACK — REWRITE REQUIRED ---\n"
        f"{rewrite_notes}\n"
        f"--- END CRITIC FEEDBACK ---"
    )

    from app.services.openrouter_generator import generate_platform_content
    new_content = await generate_platform_content(augmented_utd, brand_voice)

    critic_result = await critic_with_hitl(
        generated_content=new_content,
        original_utd=original_utd,
        brand_voice=brand_voice,
        agent_profile_id=action.agent_profile_id,
        client_id=action.client_id,
        db_session=db_session,
    )

    new_action_id = critic_result.get("hitl_action_id")
    if new_action_id:
        from sqlalchemy import update
        from database.models import HitlAction
        from sqlalchemy.ext.asyncio import AsyncSession

        stmt = (
            update(HitlAction)
            .where(HitlAction.id == new_action_id)
            .values(original_action_id=action.id)
        )
        if db_session:
            await db_session.execute(stmt)
            await db_session.flush()

    logger.info("Rewrite complete — original=%s replacement=%s", action.id, new_action_id)

    HITLStateMachine._validate_transition(action.status, "REWRITE_COMPLETED")
    action.status = "REWRITE_COMPLETED"
    if db_session:
        await db_session.flush()

    return {
        "status": "REWRITE_COMPLETED",
        "original_action_id": str(action.id),
        "replacement_action_id": new_action_id,
        "critic_result": critic_result,
    }
