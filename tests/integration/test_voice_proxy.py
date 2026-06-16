"""
Integration tests for the VoiceProxyAgent.
Uses monkeypatch to mock livekit_service and recall_ai methods on the
service classes so that VoiceProxyAgent (which creates instances of those
services in __init__) picks up the mocks automatically.
"""

import pytest

from app.agents.voice_agent import VoiceProxyAgent
from app.core.orchestrator import AgentContext, DAGOrchestrator
from app.services.livekit_service import LiveKitRoom, LiveKitService
from app.services.recall_ai import RecallAIService, RecallSession, RecallSessionConfig

# ---------------------------------------------------------------------------
# Mock helpers  (accept `self` because they replace bound methods on a class)
# ---------------------------------------------------------------------------

async def _mock_create_room(self, room_name: str) -> LiveKitRoom:
    return LiveKitRoom(room_name=room_name, room_sid=f"RM_{room_name}")


async def _mock_generate_token(self, room_name: str, identity: str, ttl_seconds: int = 300) -> str:
    return f"mock_livekit_token_{identity}_{room_name}"


async def _mock_close_room(self, room_name: str) -> None:
    pass


async def _mock_create_session(self, config: RecallSessionConfig) -> RecallSession:
    return RecallSession(
        session_id=f"recall_{config.meeting_url[:8]}",
        status="running",
        meeting_url=config.meeting_url,
        platform=config.platform,
    )


async def _mock_get_transcript(self, session_id: str) -> str:
    return "Mock transcript for testing purposes."


async def _mock_stop_session(self, session_id: str) -> bool:
    return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voice_agent_registers(monkeypatch):
    """Verify VoiceProxyAgent can be registered in the DAGOrchestrator."""
    monkeypatch.setattr(LiveKitService, "create_room", _mock_create_room)
    monkeypatch.setattr(LiveKitService, "generate_token", _mock_generate_token)

    orchestrator = DAGOrchestrator()
    agent = VoiceProxyAgent()
    orchestrator.register(agent)

    assert "voice_proxy_agent" in orchestrator._agents
    assert "voice_proxy_agent" in orchestrator._nodes
    node = orchestrator._nodes["voice_proxy_agent"]
    assert node.status.value == "pending"


@pytest.mark.asyncio
async def test_voice_agent_context(monkeypatch):
    """Verify the agent populates ctx.metadata with session info."""
    monkeypatch.setattr(LiveKitService, "create_room", _mock_create_room)
    monkeypatch.setattr(LiveKitService, "generate_token", _mock_generate_token)
    monkeypatch.setattr(LiveKitService, "close_room", _mock_close_room)
    monkeypatch.setattr(RecallAIService, "create_session", _mock_create_session)

    orchestrator = DAGOrchestrator()
    agent = VoiceProxyAgent()
    orchestrator.register(agent)

    ctx = AgentContext(
        topic="voice_session",
        metadata={
            "session_id": "test-session-001",
            "client_id": "test-client",
            "meeting_url": "https://zoom.us/j/123456789",
        },
    )

    result = await orchestrator.run(ctx)

    assert result.metadata.get("session_id") == "test-session-001"
    assert result.metadata.get("livekit_room") == "test-session-001"
    assert result.metadata.get("livekit_token") is not None
    assert result.metadata.get("livekit_token").startswith("mock_livekit_token_")
    assert result.metadata.get("recall_session_id") == "recall_https://"


@pytest.mark.asyncio
async def test_voice_agent_handles_livekit_failure(monkeypatch):
    """Verify the agent logs an error and raises when LiveKit room creation fails."""
    async def failing_create_room(self, room_name: str):
        raise RuntimeError("LiveKit API unavailable")

    monkeypatch.setattr(LiveKitService, "create_room", failing_create_room)

    orchestrator = DAGOrchestrator()
    agent = VoiceProxyAgent()
    orchestrator.register(agent)

    ctx = AgentContext(
        topic="voice_session",
        metadata={
            "client_id": "fail-client",
        },
    )

    with pytest.raises(RuntimeError, match="LiveKit API unavailable"):
        await orchestrator.run(ctx)

    assert len(ctx.errors) > 0
    assert "livekit_room_creation_failed" in ctx.errors[0]["error"]


@pytest.mark.asyncio
async def test_voice_agent_no_meeting_url(monkeypatch):
    """Verify the agent works without a meeting URL (no Recall.ai bot)."""
    monkeypatch.setattr(LiveKitService, "create_room", _mock_create_room)
    monkeypatch.setattr(LiveKitService, "generate_token", _mock_generate_token)
    monkeypatch.setattr(LiveKitService, "close_room", _mock_close_room)

    orchestrator = DAGOrchestrator()
    agent = VoiceProxyAgent()
    orchestrator.register(agent)

    ctx = AgentContext(
        topic="voice_session",
        metadata={
            "client_id": "no-meeting-client",
        },
    )

    result = await orchestrator.run(ctx)

    assert result.metadata.get("livekit_room") is not None
    assert result.metadata.get("livekit_token") is not None
    assert result.metadata.get("recall_session_id") is None
    assert len(result.errors) == 0
