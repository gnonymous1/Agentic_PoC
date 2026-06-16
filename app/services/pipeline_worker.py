"""
Background worker for async content pipeline processing.
Dequeues jobs from the pipeline queue and executes the full DAG.
"""

from app.config import settings
from app.models.agent_contracts import ResearchContract
from app.services.critic_loop import MaxRetriesExceededError, critic_verification_loop
from app.services.gemini_grounding import research_topic
from app.services.openrouter_generator import generate_platform_content
from app.services.redis_queue import task_queue

PIPELINE_QUEUE = "manufacture:pipeline"


async def process_job(job_data: dict) -> dict:
    topic = job_data.get("topic", "")
    brand_voice = job_data.get("brand_voice")
    client_id = job_data.get("client_id", "")

    research_result = await research_topic(topic, brand_voice)
    contract = ResearchContract(
        topic=topic,
        unified_truth_document=research_result,
    )

    content = await generate_platform_content(
        contract.unified_truth_document, brand_voice
    )

    try:
        final_content, cycles = await critic_verification_loop(
            content, contract.unified_truth_document, brand_voice
        )
        approved = True
        refinement_notes = ""
    except MaxRetriesExceededError as e:
        approved = False
        cycles = settings.max_retries
        refinement_notes = e.last_refinement_notes

    result = {
        "status": "approved" if approved else "rejected",
        "critic_cycles": cycles,
        "refinement_notes": refinement_notes,
    }

    from app.infrastructure.cache import cache
    await cache.set(
        f"pipeline:result:{job_data.get('job_id', 'unknown')}",
        result,
        ttl=3600,
    )
    return result


async def worker_loop():
    await task_queue.process(PIPELINE_QUEUE, process_job)
