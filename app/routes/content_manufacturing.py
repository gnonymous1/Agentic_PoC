import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.agents.copywriting_agent import CopywritingAgent
from app.agents.critic_agent import CriticAgent
from app.agents.moderator_agent import ModeratorAgent
from app.agents.research_agent import ResearchAgent
from app.core.orchestrator import AgentContext, DAGOrchestrator
from app.schemas import ContentRequest, ContentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Content Manufacturing"])

_manufacturing_pipeline = DAGOrchestrator()
_manufacturing_pipeline.register(ResearchAgent())
_manufacturing_pipeline.register(CopywritingAgent(), depends_on=["research_agent"])
_manufacturing_pipeline.register(CriticAgent(), depends_on=["copywriting_agent"])
_manufacturing_pipeline.register(ModeratorAgent(), depends_on=["critic_agent"])


@router.post("/manufacture", response_model=ContentResponse)
async def manufacture_content(request: ContentRequest):
    request_id = str(uuid.uuid4())
    logger.info(
        "Manufacturing content [%s] for topic: %.80s",
        request_id,
        request.topic,
    )

    ctx = AgentContext(
        correlation_id=request_id,
        topic=request.topic,
        brand_voice=request.brand_voice_override or "",
    )

    try:
        ctx = await _manufacturing_pipeline.run(ctx)
    except Exception as e:
        logger.error("Pipeline failed for [%s]: %s", request_id, str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Content manufacturing pipeline failed",
                "correlation_id": request_id,
                "detail": str(e),
            },
        )

    return ContentResponse(
        request_id=request_id,
        topic=request.topic,
        unified_truth_document=ctx.unified_truth_document,
        prompt_hashes={},
        generated_content=ctx.generated_content,
        critic_approved=ctx.critic_approved,
        refinement_cycles=ctx.refinement_cycles,
    )


@router.get("/health")
async def health_check():
    return {"status": "operational", "service": "GNONE Content Manufacturing Loop"}
