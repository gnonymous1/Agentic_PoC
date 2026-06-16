from app.services.livekit_service import LiveKitRoom


async def mock_create_room(room_name: str) -> LiveKitRoom:
    return LiveKitRoom(room_name=room_name, room_sid=f"RM_{room_name}")


async def mock_generate_token(room_name: str, identity: str, ttl_seconds: int = 300) -> str:
    return f"mock_livekit_token_{identity}_{room_name}"


async def mock_close_room(room_name: str):
    pass
