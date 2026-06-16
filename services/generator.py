"""
Persona-aware content generator orchestrator.
Wraps the existing Research → Copywriting pipeline with clone profile awareness.
"""

import json
import logging
from typing import Optional
from uuid import UUID, uuid4

from database.models import AgentProfile, CorporateKnowledgeVector, HitlAction
from app.services.gemini_grounding import research_topic
from app.services.openrouter_generator import generate_platform_content
from app.core.orchestrator import DAGOrchestrator, AgentContext
from app.agents.research_agent import ResearchAgent
from app.agents.copywriting_agent import CopywritingAgent
from app.agents.critic_agent import CriticAgent
from app.agents.moderator_agent import ModeratorAgent

logger = logging.getLogger(__name__)


class CloneGenerator:
    """
    Generates content on behalf of a specific clone profile.
    Injects persona system prompts, knowledge context, and brand guardrails.
    """

    def __init__(self, agent_profile: AgentProfile):
        self.profile = agent_profile
        self.client_id = agent_profile.client_id
        self.profile_id = agent_profile.id
        self.agent_name = agent_profile.agent_name
        self.system_prompt = agent_profile.system_prompt
        self.guardrails = agent_profile.guardrails or {}

    async def research_with_persona(
        self,
        topic: str,
        knowledge_context: Optional[str] = None,
    ) -> str:
        """
        Perform web-grounded research enhanced with the persona's knowledge context.
        Returns a Unified Truth Document tailored to this clone's perspective.
        """
        augmented_topic = topic
        if self.system_prompt:
            augmented_topic = (
                f"{topic}\n\n"
                f"PERSONA CONTEXT — You are generating this research for:\n"
                f"{self.agent_name}\n"
                f"System Prompt: {self.system_prompt[:500]}\n"
                f"Brand Tone: {self.guardrails.get('brand_tone', 'professional')}\n"
            )
        if knowledge_context:
            augmented_topic += f"\n\nKnowledge Context:\n{knowledge_context[:2000]}"

        utd = await research_topic(augmented_topic)
        return utd

    async def generate_persona_content(
        self,
        utd: str,
        brand_voice_override: Optional[str] = None,
    ) -> dict:
        """
        Generate multi-platform content in the clone's voice.
        The brand_voice is augmented with the persona's system prompt.
        """
        effective_brand_voice = brand_voice_override or self.guardrails.get("brand_tone", "professional")

        if self.system_prompt:
            effective_brand_voice = (
                f"{effective_brand_voice}\n\n"
                f"CLONE PERSONA: {self.agent_name}\n"
                f"Persona Instructions: {self.system_prompt[:1000]}"
            )

        content = await generate_platform_content(utd, effective_brand_voice)
        return content.model_dump()

    async def full_pipeline(
        self,
        topic: str,
        brand_voice_override: Optional[str] = None,
        knowledge_context: Optional[str] = None,
    ) -> AgentContext:
        """
        Run the full DAG pipeline (Research → Copywriting → Critic → Moderator)
        with persona-aware context injection.
        """
        utd = await self.research_with_persona(topic, knowledge_context)
        content = await self.generate_persona_content(utd, brand_voice_override)

        orchestrator = DAGOrchestrator()
        orchestrator.register(ResearchAgent())
        orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])
        orchestrator.register(CriticAgent(), depends_on=["copywriting_agent"])
        orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

        ctx = AgentContext(
            topic=topic,
            brand_voice=brand_voice_override or self.guardrails.get("brand_tone", "professional"),
        )
        ctx.unified_truth_document = utd
        ctx.generated_content = content

        result = await orchestrator.run(ctx)
        return result

    async def create_hitl_action(
        self,
        action_type: str,
        payload: dict,
        target_platform: Optional[str] = None,
        db_session=None,
    ) -> HitlAction:
        """
        Record a generated action as PENDING_HUMAN_SIGN_OFF in the HITL ledger.
        """
        hitl = HitlAction(
            client_id=self.client_id,
            agent_profile_id=self.profile_id,
            action_type=action_type,
            status="PENDING_HUMAN_SIGN_OFF",
            payload=payload,
            target_platform=target_platform,
        )
        if db_session:
            db_session.add(hitl)
            await db_session.flush()
            logger.info(
                "HITL action created — id=%s type=%s status=PENDING_HUMAN_SIGN_OFF",
                hitl.id, action_type,
            )
        return hitl
