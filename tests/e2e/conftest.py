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
from app.core.orchestrator import DAGOrchestrator
from tests.mocks.mock_critic import (
    mock_call_critic_correct,
    mock_call_critic_eval,
    mock_critic_verification_loop,
)
from tests.mocks.mock_gemini import mock_research_topic
from tests.mocks.mock_openrouter import mock_generate_platform_content


@pytest.fixture
def sample_topics():
    return [
        "AI in Healthcare 2026",
        "Sustainable Energy Storage",
        "Quantum Computing Forecast",
    ]


@pytest.fixture
def orchestrator():
    o = DAGOrchestrator()
    o.register(ResearchAgent())
    o.register(CopywritingAgent(), depends_on=["research_agent"])
    o.register(CriticAgent(), depends_on=["copywriting_agent"])
    o.register(ModeratorAgent(), depends_on=["critic_agent"])
    return o


@pytest.fixture
def apply_mocks(monkeypatch):
    monkeypatch.setattr(gg, "research_topic", mock_research_topic)
    monkeypatch.setattr(ra, "research_topic", mock_research_topic)
    monkeypatch.setattr(og, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(ca, "generate_platform_content", mock_generate_platform_content)
    monkeypatch.setattr(cl, "call_critic_eval", mock_call_critic_eval)
    monkeypatch.setattr(cl, "call_critic_correct", mock_call_critic_correct)
    monkeypatch.setattr(cra, "critic_verification_loop", mock_critic_verification_loop)
