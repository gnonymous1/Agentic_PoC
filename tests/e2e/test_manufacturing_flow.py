import pytest

import app.agents.copywriting_agent as ca
import app.agents.critic_agent as cra
import app.agents.research_agent as ra
import app.services.critic_loop as cl
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

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_full_pipeline_with_all_agents(monkeypatch):
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
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    ctx = await orchestrator.run(AgentContext(
        topic="AI in Healthcare 2026",
        brand_voice="Professional, authoritative",
    ))

    assert ctx.unified_truth_document
    assert "Unified Truth Document" in ctx.unified_truth_document
    assert ctx.generated_content
    assert "twitter" in ctx.generated_content
    assert "linkedin" in ctx.generated_content
    assert "facebook" in ctx.generated_content
    assert "blogspot" in ctx.generated_content
    assert ctx.critic_approved is not None
    verdict = ctx.get("moderator_verdict")
    assert verdict is not None
    assert verdict.get("passed_safety_check") is True


@pytest.mark.asyncio
async def test_pipeline_content_quality(monkeypatch):
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
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    ctx = await orchestrator.run(AgentContext(topic="AI in Healthcare 2026"))

    content = ctx.generated_content
    assert len(content["twitter"]["posts"]) >= 5
    for post in content["twitter"]["posts"]:
        assert len(post.strip()) <= 240

    assert len(content["linkedin"]["body"]) >= 50
    assert len(content["facebook"]["body"]) >= 50

    import re
    html_body = content["blogspot"]["html_body"]
    text = re.sub(r"<[^>]+>", "", html_body)
    word_count = len(text.split())
    assert word_count >= 600, f"Blogspot html_body has {word_count} words, expected >= 600"


@pytest.mark.asyncio
async def test_pipeline_with_different_topics(monkeypatch, sample_topics):
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
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    for topic in sample_topics:
        ctx = await orchestrator.run(AgentContext(topic=topic))
        assert ctx.unified_truth_document
        assert ctx.generated_content
        assert ctx.critic_approved is not None
        verdict = ctx.get("moderator_verdict")
        assert verdict is not None


@pytest.mark.asyncio
async def test_pipeline_idempotency(monkeypatch):
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
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    ctx1 = await orchestrator.run(AgentContext(topic="AI in Healthcare 2026"))
    ctx2 = await orchestrator.run(AgentContext(topic="AI in Healthcare 2026"))

    assert ctx1.get("correlation_id") != ctx2.get("correlation_id")


@pytest.mark.asyncio
async def test_pipeline_handles_topic_edge_cases(monkeypatch):
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
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    edge_cases = [
        "Hello World",  # 11 chars, barely above min
        "A" * 2000,  # max length
        "Tech & AI: 2026's #1 Trend! @everyone",  # special chars
    ]
    for topic in edge_cases:
        ctx = await orchestrator.run(AgentContext(topic=topic))
        assert ctx.generated_content, f"Pipeline failed for topic: {topic[:50]}"


@pytest.mark.asyncio
async def test_pipeline_critic_rejects_then_accepts(monkeypatch):
    monkeypatch.setattr(gg, "research_topic", mock_research_topic)
    monkeypatch.setattr(ra, "research_topic", mock_research_topic)
    monkeypatch.setattr(og, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(ca, "generate_platform_content", mock_generate_platform_content)

    call_count = 0

    async def rejecting_then_accepting_eval(content):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            from app.services.critic_loop import CriticResult
            return CriticResult(approved=False, refinement_notes="Fix fluff phrases", corrected_payloads={})
        return await mock_call_critic_eval(content)

    async def correcting_eval(content, notes):
        from app.services.critic_loop import CriticResult
        return CriticResult(approved=False, refinement_notes="", corrected_payloads=content.model_dump())

    monkeypatch.setattr(cl, "call_critic_eval", rejecting_then_accepting_eval)
    monkeypatch.setattr(cl, "call_critic_correct", correcting_eval)
    # Do NOT patch critic_verification_loop — let it run the actual loop with mocked eval/correct

    orchestrator = DAGOrchestrator()
    orchestrator.register(ResearchAgent())
    orchestrator.register(CopywritingAgent(), depends_on=["research_agent"])
    orchestrator.register(CriticAgent(), depends_on=["copywriting_agent"])
    orchestrator.register(ModeratorAgent(), depends_on=["critic_agent"])

    ctx = await orchestrator.run(AgentContext(topic="AI in Healthcare 2026"))
    assert ctx.critic_approved is True
