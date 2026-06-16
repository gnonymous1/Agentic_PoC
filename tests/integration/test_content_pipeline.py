"""
Integration tests for the full content manufacturing pipeline.
Uses mock services to avoid real API calls.
"""

import pytest

import app.agents.copywriting_agent as ca
import app.agents.critic_agent as cra
import app.agents.research_agent as ra
import app.services.critic_loop as cl

# Patch service functions with mocks — both module-level and agent-level
import app.services.gemini_grounding as gg
import app.services.openrouter_generator as og
from app.agents.copywriting_agent import CopywritingAgent
from app.agents.critic_agent import CriticAgent
from app.agents.moderator_agent import ModeratorAgent
from app.agents.research_agent import ResearchAgent
from app.core.orchestrator import AgentContext, DAGOrchestrator
from tests.mocks.mock_critic import (
    mock_call_critic_correct,
    mock_call_critic_eval,
    mock_critic_verification_loop,
)
from tests.mocks.mock_gemini import mock_research_topic
from tests.mocks.mock_openrouter import mock_generate_platform_content


@pytest.mark.asyncio
async def test_full_content_pipeline(monkeypatch):
    monkeypatch.setattr(gg, "research_topic", mock_research_topic)
    monkeypatch.setattr(ra, "research_topic", mock_research_topic)
    monkeypatch.setattr(og, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(ca, "generate_platform_content", mock_generate_platform_content)

    orchestrator = DAGOrchestrator()
    orchestrator.register(ResearchAgent())
    orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])

    ctx = await orchestrator.run(AgentContext(
        topic="AI Landscape 2026",
        brand_voice="Professional, authoritative, data-driven",
    ))

    assert ctx.unified_truth_document
    assert "Unified Truth Document" in ctx.unified_truth_document
    assert ctx.generated_content
    assert "twitter" in ctx.generated_content
    assert "linkedin" in ctx.generated_content
    assert "facebook" in ctx.generated_content
    assert "blogspot" in ctx.generated_content


@pytest.mark.asyncio
async def test_pipeline_with_critic(monkeypatch):
    monkeypatch.setattr(gg, "research_topic", mock_research_topic)
    monkeypatch.setattr(ra, "research_topic", mock_research_topic)
    monkeypatch.setattr(og, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(ca, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(cl, "call_critic_eval", mock_call_critic_eval)
    monkeypatch.setattr(cl, "call_critic_correct", mock_call_critic_correct)
    monkeypatch.setattr(cra, "critic_verification_loop", mock_critic_verification_loop)

    orchestrator = DAGOrchestrator()
    orchestrator.register(ResearchAgent())
    orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])
    orchestrator.register(CriticAgent(), depends_on=["copywriting_agent"])

    ctx = await orchestrator.run(AgentContext(topic="Test topic"))
    assert ctx.critic_approved is not None
    assert ctx.generated_content


@pytest.mark.asyncio
async def test_pipeline_with_moderator(monkeypatch):
    monkeypatch.setattr(gg, "research_topic", mock_research_topic)
    monkeypatch.setattr(ra, "research_topic", mock_research_topic)
    monkeypatch.setattr(og, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(ca, "generate_platform_content", mock_generate_platform_content)

    orchestrator = DAGOrchestrator()
    orchestrator.register(ResearchAgent())
    orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])
    orchestrator.register(ModeratorAgent(), depends_on=["copywriting_agent"])

    ctx = await orchestrator.run(AgentContext(topic="Test topic"))

    verdict = ctx.get("moderator_verdict")
    assert verdict is not None
    assert verdict.get("passed_safety_check") is True
