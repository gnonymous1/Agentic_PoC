from app.services.recall_ai import RecallSession, RecallSessionConfig


async def mock_create_session(config: RecallSessionConfig) -> RecallSession:
    return RecallSession(
        session_id=f"recall_{config.meeting_url[:8]}",
        status="running",
        meeting_url=config.meeting_url,
        platform=config.platform,
    )


async def mock_get_transcript(session_id: str) -> str:
    return "Mock transcript for testing purposes."


async def mock_stop_session(session_id: str) -> bool:
    return True
