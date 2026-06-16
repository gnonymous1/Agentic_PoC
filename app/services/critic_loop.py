import asyncio
import difflib
import json
import logging
import random
import time

import httpx

from app.config import settings
from app.core.circuit_breaker import CircuitBreaker, breaker_manager
from app.models.content_models import MultiPlatformContent

logger = logging.getLogger(__name__)

CRITIC_EVAL_PROMPT = """You are an Asymmetric Critic operating inside the Sovereign Executive Proxy Engine. Your function is adversarial quality assurance on generated multi-platform marketing content.

Analyze the provided JSON object containing drafts for Twitter, LinkedIn, Facebook, and Blogspot. You must detect and flag:

1. **Generic AI Hallmarks** — any occurrence of these banned phrases counts as a defect:
   "delve", "testament to", "in conclusion", "revolutionizing", "moreover",
   "groundbreaking", "game-changer", "cutting-edge", "leverage", "synergy",
   "paradigm shift", "utilize", "in today's", "in the ever-evolving",
   "it is important to note", "furthermore".

2. **Grammatical & Layout Alignment Breaks** — run-on sentences, inconsistent capitalization, broken markdown, malformed bullet lists, missing line breaks in LinkedIn body, posts that exceed 240 characters on Twitter.

3. **Structural / Code Flaws** — missing required fields, truncated HTML tags in blogspot.html_body, arrays that violate length constraints (twitter.posts must be 5-10 items).

4. **Brand Voice Drift** — tone inconsistent with the presumed professional/executive brand positioning.

Return *only* a raw JSON object — no markdown fences, no explanation — conforming exactly to:

{
  "approved": true,
  "refinement_notes": ""
}

If the content passes all checks, set `approved: true`.
If the content fails, set `approved: false` and populate `refinement_notes` with a bullet-point list of specific issues and the exact fix required for each.

Be strict. A false positive (rejecting good content) is better than a false negative (shipping fluff)."""

CRITIC_CORRECT_PROMPT = """You are an Asymmetric Critic operating in correction mode. Your job is to repair content that failed initial evaluation.

You will receive:
- `original_content`: The full multi-platform content object that was rejected.
- `refinement_notes`: A detailed list of issues that need to be fixed.

Apply ALL fixes described in the refinement_notes. Return *only* a raw JSON object — no markdown fences, no explanation — conforming exactly to:

{
  "corrected_payloads": {
    "twitter": { "posts": [...] },
    "linkedin": { "body": "...", "hashtags": [...] },
    "facebook": { "body": "...", "call_to_action": "..." },
    "blogspot": { "title": "...", "seo_slug": "...", "meta_description": "...", "html_body": "..." }
  }
}

Rules:
- Fix every issue listed in refinement_notes without introducing new problems.
- Preserve all facts and data from the original content.
- Maintain the same overall structure and field types.
- Never add banned fluff phrases."""

breaker_manager.register("critic", CircuitBreaker("critic"))

MAX_429_RETRIES = 5


async def _call_critic_api(payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://gnone.local",
        "X-Title": "GNONE Critic Loop",
    }
    for attempt in range(1, MAX_429_RETRIES + 1):
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            response = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "1")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = 1.0
                jitter = random.uniform(0, 0.5)
                logger.warning(
                    "429 on critic API (attempt %d/%d), retrying in %.2fs",
                    attempt, MAX_429_RETRIES, delay + jitter,
                )
                await asyncio.sleep(delay + jitter)
                continue
            response.raise_for_status()
            return response.json()
    raise RuntimeError("Exhausted 429 retries for Critic API")


class CriticResult:
    def __init__(self, approved: bool, refinement_notes: str, corrected_payloads: dict):
        self.approved = approved
        self.refinement_notes = refinement_notes
        self.corrected_payloads = corrected_payloads

    @classmethod
    def from_dict(cls, data: dict) -> "CriticResult":
        return cls(
            approved=bool(data.get("approved", False)),
            refinement_notes=str(data.get("refinement_notes", "")),
            corrected_payloads=data.get("corrected_payloads", {}),
        )


async def call_critic_eval(content: MultiPlatformContent) -> CriticResult:
    payload = {
        "model": settings.critic_model,
        "messages": [
            {"role": "system", "content": CRITIC_EVAL_PROMPT},
            {
                "role": "user",
                "content": json.dumps(content.model_dump(), indent=2),
            },
        ],
        "temperature": 0.0,
        "max_tokens": settings.critic_max_tokens,
        "response_format": {"type": "json_object"},
    }

    async def _do_eval():
        data = await _call_critic_api(payload)
        raw = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return json.loads(raw)

    parsed = await breaker_manager.call_with_fallback("critic", _do_eval)
    return CriticResult(
        approved=bool(parsed.get("approved", False)),
        refinement_notes=str(parsed.get("refinement_notes", "")),
        corrected_payloads={},
    )


async def call_critic_correct(content: MultiPlatformContent, refinement_notes: str) -> CriticResult:
    correction_input = {
        "original_content": content.model_dump(),
        "refinement_notes": refinement_notes,
    }
    payload = {
        "model": settings.critic_model,
        "messages": [
            {"role": "system", "content": CRITIC_CORRECT_PROMPT},
            {
                "role": "user",
                "content": json.dumps(correction_input, indent=2),
            },
        ],
        "temperature": 0.3,
        "max_tokens": settings.critic_max_tokens,
        "response_format": {"type": "json_object"},
    }

    async def _do_correct():
        data = await _call_critic_api(payload)
        raw = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return json.loads(raw)

    parsed = await breaker_manager.call_with_fallback("critic", _do_correct)
    return CriticResult(
        approved=False,
        refinement_notes="",
        corrected_payloads=parsed.get("corrected_payloads", {}),
    )


async def regenerate_with_feedback(
    original_utd: str,
    refinement_notes: str,
    brand_voice: str | None = None,
) -> MultiPlatformContent:
    from app.services.openrouter_generator import generate_platform_content

    augmented_utd = (
        f"{original_utd}\n\n"
        f"--- CRITIC FEEDBACK — APPLY THESE CORRECTIONS ---\n"
        f"{refinement_notes}\n"
        f"--- END CRITIC FEEDBACK ---"
    )
    return await generate_platform_content(augmented_utd, brand_voice)


class MaxRetriesExceededError(Exception):
    def __init__(self, last_refinement_notes: str = ""):
        self.last_refinement_notes = last_refinement_notes
        super().__init__(
            f"Content failed critic verification after "
            f"{settings.max_retries} retries."
        )


async def critic_verification_loop(
    generated: MultiPlatformContent,
    original_utd: str,
    brand_voice: str | None = None,
    deadline: float | None = None,
) -> tuple[MultiPlatformContent, int]:
    if deadline is None:
        deadline = settings.request_timeout_seconds - settings.deadline_buffer_seconds

    start = time.monotonic()
    previous_dump = None
    result = None

    for attempt in range(1, settings.max_retries + 1):
        elapsed = time.monotonic() - start
        if elapsed >= deadline:
            raise MaxRetriesExceededError(
                "Deadline exceeded" if result is None else result.refinement_notes
            )

        logger.info("Critic verification attempt %d/%d", attempt, settings.max_retries)

        current_dump = generated.model_dump()
        extra_directives = ""
        if previous_dump is not None:
            similarity = difflib.SequenceMatcher(
                None,
                json.dumps(previous_dump, sort_keys=True),
                json.dumps(current_dump, sort_keys=True),
            ).ratio()
            if similarity > 0.95:
                extra_directives = (
                    "\n\nCRITICAL: Previous iteration produced nearly identical output. "
                    "You MUST make substantive changes. Avoid all banned phrases. "
                    "Rewrite creatively while preserving facts."
                )
                logger.warning(
                    "Oscillation detected (similarity=%.3f), injecting stronger directives",
                    similarity,
                )
        previous_dump = current_dump

        result = await call_critic_eval(generated)

        if result.approved:
            logger.info("Content approved on attempt %d", attempt)
            return generated, attempt

        logger.warning(
            "Critic rejected content on attempt %d: %s",
            attempt,
            result.refinement_notes[:200],
        )

        refinement = result.refinement_notes
        if extra_directives:
            refinement += extra_directives

        correction_result = await call_critic_correct(generated, refinement)
        if correction_result.corrected_payloads:
            generated = MultiPlatformContent.model_validate(
                correction_result.corrected_payloads
            )
        else:
            generated = await regenerate_with_feedback(
                original_utd, refinement, brand_voice
            )

    raise MaxRetriesExceededError(
        result.refinement_notes if result is not None else ""
    )
