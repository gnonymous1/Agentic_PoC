"""Mock client for Critic loop API testing with input validation."""

from app.models.content_models import MultiPlatformContent
from app.services.critic_loop import CriticResult


async def mock_call_critic_eval(content: MultiPlatformContent) -> CriticResult:
    if not isinstance(content, MultiPlatformContent):
        raise TypeError("content must be a MultiPlatformContent instance")
    return CriticResult(approved=True, refinement_notes="", corrected_payloads={})


async def mock_call_critic_correct(
    content: MultiPlatformContent, refinement_notes: str
) -> CriticResult:
    if not isinstance(content, MultiPlatformContent):
        raise TypeError("content must be a MultiPlatformContent instance")
    return CriticResult(
        approved=False,
        refinement_notes="",
        corrected_payloads=content.model_dump(),
    )


async def mock_critic_verification_loop(
    generated: MultiPlatformContent,
    original_utd: str,
    brand_voice: str = None,
    deadline: float = None,
) -> tuple[MultiPlatformContent, int]:
    if not isinstance(generated, MultiPlatformContent):
        raise TypeError("generated must be a MultiPlatformContent instance")
    return generated, 1
