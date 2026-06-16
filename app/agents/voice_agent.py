from uuid import uuid4

from app.agents.base import BaseAgent
from app.core.orchestrator import AgentContext
from app.services.livekit_service import LiveKitService
from app.services.recall_ai import RecallAIService, RecallSessionConfig


class VoiceProxyAgent(BaseAgent):
    """
    Real-Time Voice Proxy Agent.
    Connects inside the LiveKit transport track to listen to call participants,
    handle verbal interruptions, track screen-shares visually, and respond
    using an optimized custom voice clone.

    Expects ``ctx.metadata`` to contain:
        - ``session_id`` (str, optional) — will be auto-generated if absent
        - ``client_id`` (str) — identity label for LiveKit participant
        - ``meeting_url`` (str, optional) — if provided, a Recall.ai bot is
          spawned for the meeting
    """

    def __init__(self):
        super().__init__(name="voice_proxy_agent")
        self._livekit = LiveKitService()
        self._recall = RecallAIService()

    async def execute(self, ctx: AgentContext) -> AgentContext:
        session_id = ctx.metadata.get("session_id") or str(uuid4())
        client_id = ctx.metadata.get("client_id", "unknown")
        meeting_url = ctx.metadata.get("meeting_url", "")
        identity = f"agent-{client_id}"

        self.logger.info(
            "Starting voice proxy | session=%s client=%s",
            session_id, client_id,
        )

        room_name = None
        token = None
        recall_session_id = None

        # 1. Create a LiveKit room for this session
        try:
            room = await self._livekit.create_room(session_id)
            room_name = room.room_name
            self.logger.info("LiveKit room created: %s", room_name)
        except Exception as exc:
            self.logger.error("Failed to create LiveKit room: %s", exc)
            ctx.errors.append({
                "agent": self.name,
                "error": f"livekit_room_creation_failed: {exc}",
                "correlation_id": ctx.correlation_id,
            })
            raise

        # 2. Generate a LiveKit access token for the agent
        try:
            token = await self._livekit.generate_token(room_name, identity)
            self.logger.info("LiveKit token generated for identity=%s", identity)
        except Exception as exc:
            self.logger.error("Failed to generate LiveKit token: %s", exc)
            ctx.errors.append({
                "agent": self.name,
                "error": f"livekit_token_generation_failed: {exc}",
                "correlation_id": ctx.correlation_id,
            })
            raise

        # 3. Optionally start a Recall.ai bot if a meeting URL was provided
        if meeting_url:
            try:
                config = RecallSessionConfig(meeting_url=meeting_url)
                recall_session = await self._recall.create_session(config)
                recall_session_id = recall_session.session_id
                self.logger.info("Recall.ai session started: %s", recall_session_id)
            except Exception as exc:
                self.logger.warning(
                    "Recall.ai session failed (non-fatal): %s", exc
                )
                ctx.errors.append({
                    "agent": self.name,
                    "error": f"recall_session_failed: {exc}",
                    "correlation_id": ctx.correlation_id,
                })

        # 4. Persist session details in the context
        ctx.metadata["session_id"] = session_id
        ctx.metadata["livekit_room"] = room_name
        ctx.metadata["livekit_token"] = token
        ctx.metadata["recall_session_id"] = recall_session_id

        self.logger.info(
            "Voice proxy session ready | room=%s recall=%s",
            room_name, recall_session_id or "none",
        )
        return ctx
