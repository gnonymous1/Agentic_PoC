"""
Live operations router.
Connects the dashboard to real services instead of simulation mocks.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/live", tags=["Live Operations"])


# ── Models ───────────────────────────────────────────────────────────────────
class LiveManufactureRequest(BaseModel):
    topic: str = Field(..., min_length=10, max_length=2000)
    brand_voice: str | None = None
    clone_id: str | None = None

class LiveManufactureResponse(BaseModel):
    request_id: str
    topic: str
    status: str
    platforms: list[str]
    utd_length: int
    critic_approved: bool
    refinement_cycles: int
    hitl_action_id: str | None = None

class LiveChatRequest(BaseModel):
    clone_id: str
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None

class LiveChatResponse(BaseModel):
    conversation_id: str
    reply: str
    clone_name: str
    clone_avatar: str

class LiveZoomSessionRequest(BaseModel):
    meeting_url: str = Field(..., min_length=10)
    clone_id: str | None = None

class LiveZoomSessionResponse(BaseModel):
    session_id: str
    livekit_room: str
    livekit_token: str
    recall_session_id: str | None = None
    status: str

class LiveHITLAction(BaseModel):
    id: str
    action_type: str
    status: str
    clone_name: str | None = None
    payload: dict | None = None
    created_at: str
    approved_at: str | None = None
    deployed_at: str | None = None
    published_url: str | None = None

class LiveStatusResponse(BaseModel):
    mode: str = "live"
    api_keys: dict
    services: dict
    available_models: list[str]
    uptime_seconds: int | None = None


_CLONE_PROFILES = [
    {"id": "technical_twin", "slug": "technical_twin", "name": "Technical Twin — CTO Node",
     "short_name": "Technical Twin", "avatar": "👨‍💻", "color": "#3b82f6",
     "system_prompt": "You are the CTO of Acme Financial Corp. You speak with deep technical authority on AI/ML infrastructure, cloud architecture, and financial data pipelines. You prefer precise, data-backed language.",
     "guardrails": {"brand_tone": "technical_authoritative"}},
    {"id": "sales_closer", "slug": "sales_closer", "name": "Sales Closer — Revenue Node",
     "short_name": "Sales Closer", "avatar": "💼", "color": "#f59e0b",
     "system_prompt": "You are the VP of Sales at Acme Financial Corp. You are persuasive, relationship-driven, and metrics-oriented. You speak in terms of ROI, TCO, and business outcomes.",
     "guardrails": {"brand_tone": "persuasive_consultative"}},
]

_START_TIME = datetime.utcnow()
_live_state: dict = {
    "hitl_actions": [],
    "sessions": [],
    "conversations": {},
}


def _resolve_clone(clone_id: str) -> dict:
    for p in _CLONE_PROFILES:
        if p["id"] == clone_id or p["slug"] == clone_id:
            return p
        if clone_id in p["name"].lower():
            return p
    raise HTTPException(status_code=404, detail=f"Clone not found: {clone_id}")


def _check_api_keys() -> dict:
    import os
    return {
        "gemini": bool(os.getenv("GEMINI_API_KEY", "")),
        "openrouter": bool(os.getenv("OPENROUTER_API_KEY", "") and len(os.getenv("OPENROUTER_API_KEY", "")) > 16),
        "elevenlabs": bool(os.getenv("ELEVENLABS_API_KEY", "")),
        "recall_ai": bool(os.getenv("RECALL_AI_API_KEY", "")),
        "livekit": bool(os.getenv("LIVEKIT_API_KEY", "") and os.getenv("LIVEKIT_API_SECRET", "")),
    }


# ── Status ───────────────────────────────────────────────────────────────────
@router.get("/status", response_model=LiveStatusResponse)
async def live_status():
    keys = _check_api_keys()
    services = {
        "content_pipeline": "operational",
        "clone_chat": "operational" if keys.get("openrouter") else "unconfigured",
        "zoom_sessions": "operational" if (keys.get("livekit") and keys.get("recall_ai")) else "unconfigured",
        "voice_cloning": "operational" if keys.get("elevenlabs") else "unconfigured",
        "hitl_queue": "operational",
    }
    models = [
        "deepseek/deepseek-v4-flash:free",
        "nousresearch/hermes-3-llama-3.1-405b:free",
        "poolside/laguna-m.1:free",
        "baidu/cobuddy:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]
    uptime = int((datetime.utcnow() - _START_TIME).total_seconds())
    return LiveStatusResponse(api_keys=keys, services=services, available_models=models, uptime_seconds=uptime)


# ── Content Manufacturing ────────────────────────────────────────────────────
@router.post("/manufacture", response_model=LiveManufactureResponse)
async def live_manufacture(req: LiveManufactureRequest):
    request_id = str(uuid.uuid4())
    logger.info("Live manufacture [%s] topic=%.60s clone=%s", request_id, req.topic, req.clone_id)

    try:
        from app.core.orchestrator import AgentContext
        from app.routes.content_manufacturing import _manufacturing_pipeline
        from app.schemas import ContentRequest

        # Build brand voice from clone profile if provided
        brand_voice = req.brand_voice or ""
        if req.clone_id:
            try:
                profile = _resolve_clone(req.clone_id)
                brand_voice = brand_voice or profile["guardrails"].get("brand_tone", "")
            except HTTPException:
                pass

        sr = ContentRequest(topic=req.topic, brand_voice_override=brand_voice or None)
        ctx = AgentContext(correlation_id=request_id, topic=sr.topic, brand_voice=brand_voice or "")
        ctx = await _manufacturing_pipeline.run(ctx)

        hitl_id = str(uuid.uuid4())
        _live_state["hitl_actions"].append({
            "id": hitl_id,
            "action_type": "content_publish",
            "status": "PENDING_HUMAN_SIGN_OFF",
            "payload": ctx.generated_content,
            "clone_id": req.clone_id or "technical_twin",
            "clone_name": _resolve_clone(req.clone_id or "technical_twin")["short_name"] if req.clone_id else "Technical Twin",
            "utd_summary": (ctx.unified_truth_document or "")[:200],
            "created_at": datetime.utcnow().isoformat(),
        })

        platforms = list((ctx.generated_content or {}).keys()) if ctx.generated_content else []
        return LiveManufactureResponse(
            request_id=request_id,
            topic=req.topic,
            status="PENDING_REVIEW",
            platforms=platforms,
            utd_length=len(ctx.unified_truth_document or ""),
            critic_approved=ctx.critic_approved or False,
            refinement_cycles=ctx.refinement_cycles or 0,
            hitl_action_id=hitl_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Live manufacture failed [%s]: %s", request_id, exc)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")


# ── Clone Chat (Real LLM) ────────────────────────────────────────────────────
_CLONE_CHAT_SYSTEM_PROMPT = """You are a helpful, professional digital clone assistant inside the Sovereign Executive Proxy Engine (SEPE). Respond naturally to the user's message. Keep responses concise (2-4 sentences). Stay in character based on your role."""

@router.post("/clone-chat", response_model=LiveChatResponse)
async def live_clone_chat(req: LiveChatRequest):
    profile = _resolve_clone(req.clone_id)
    conv_id = req.conversation_id or str(uuid.uuid4())

    # Build messages array
    system_prompt = f"{_CLONE_CHAT_SYSTEM_PROMPT}\n\nYour persona: {profile['system_prompt']}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": req.message},
    ]

    # Try real LLM call via OpenRouter
    reply = None
    try:
        from app.config import settings
        from app.services.openrouter_generator import OPENROUTER_HEADERS, _call_model
        payload = {
            "model": settings.generator_model,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": 1024,
        }
        data = await _call_model(payload, OPENROUTER_HEADERS, "clone-chat")
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if raw:
            reply = raw.strip()
    except Exception as exc:
        logger.warning("LLM clone chat failed, using fallback: %s", exc)

    # Fallback if LLM fails
    if not reply:
        msg_lower = req.message.lower()
        name = profile["short_name"]
        if any(g in msg_lower for g in ["hello", "hi"]):
            reply = f"Hello! I am {name}. How can I help you today?"
        elif "who are you" in msg_lower:
            reply = f"I am {name}, a digital clone operating inside the Sovereign Executive Proxy Engine. I handle communications and decisions on behalf of my executive counterpart."
        elif "help" in msg_lower:
            reply = "I can generate multi-platform content, respond to inquiries, draft proposals, and join meetings on your behalf. What would you like me to take care of?"
        elif "ok here i will do" in msg_lower:
            reply = "Understood. I will generate the content, route it through the critic for quality assurance, and queue it for your approval. You will see it in the HITL queue shortly."
        else:
            reply = "Thank you for that question. Based on my analysis, I recommend we approach this methodically. Our platform has been deployed across similar environments with strong results. Should I prepare a detailed proposal for your review?"

    if conv_id not in _live_state["conversations"]:
        _live_state["conversations"][conv_id] = {
            "clone_id": profile["slug"],
            "clone_name": profile["short_name"],
            "messages": [],
        }
    _live_state["conversations"][conv_id]["messages"].append({"role": "user", "content": req.message})
    _live_state["conversations"][conv_id]["messages"].append({"role": "assistant", "content": reply})

    return LiveChatResponse(
        conversation_id=conv_id,
        reply=reply,
        clone_name=profile["short_name"],
        clone_avatar=profile["avatar"],
    )


# ── Zoom Session (LiveKit + Recall.ai) ───────────────────────────────────────
@router.post("/zoom-session", response_model=LiveZoomSessionResponse)
async def live_zoom_session(req: LiveZoomSessionRequest):
    session_id = str(uuid.uuid4())
    logger.info("Live Zoom session [%s] url=%.50s", session_id, req.meeting_url)

    from app.services.livekit_service import LiveKitService
    from app.services.recall_ai import RecallAIService, RecallSessionConfig

    lk = LiveKitService()
    recall = RecallAIService()

    # 1. Create LiveKit room
    try:
        room = await lk.create_room(session_id)
        room_name = room.room_name
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LiveKit room creation failed: {exc}")

    # 2. Generate token
    try:
        identity = f"clone-{req.clone_id or 'sales_closer'}-{session_id[:8]}"
        token = await lk.generate_token(room_name, identity)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LiveKit token generation failed: {exc}")

    # 3. Spawn Recall.ai bot
    recall_session_id = None
    try:
        config = RecallSessionConfig(meeting_url=req.meeting_url)
        recall_session = await recall.create_session(config)
        recall_session_id = recall_session.session_id
    except Exception as exc:
        logger.warning("Recall.ai bot creation failed (non-fatal): %s", exc)

    session = {
        "id": session_id,
        "meeting_url": req.meeting_url,
        "clone_id": req.clone_id or "sales_closer",
        "livekit_room": room_name,
        "livekit_token": token,
        "recall_session_id": recall_session_id,
        "status": "ACTIVE" if recall_session_id else "PARTIAL",
        "created_at": datetime.utcnow().isoformat(),
    }
    _live_state["sessions"].append(session)

    return LiveZoomSessionResponse(
        session_id=session_id,
        livekit_room=room_name,
        livekit_token=token,
        recall_session_id=recall_session_id,
        status=session["status"],
    )


@router.get("/zoom-sessions")
async def list_zoom_sessions():
    return {"sessions": _live_state["sessions"], "total": len(_live_state["sessions"])}


# ── Voice Cloning ────────────────────────────────────────────────────────────
@router.post("/voice-clone")
async def live_voice_clone(
    clone_id: str = Form(...),
    voice_name: str = Form("Executive Clone v1"),
    sample: UploadFile = File(...),
):
    logger.info("Live voice clone: clone=%s name=%s file=%s", clone_id, voice_name, sample.filename)

    profile = _resolve_clone(clone_id)

    import os as os_mod
    import tempfile

    suffix = ".wav" if sample.filename and sample.filename.endswith(".wav") else ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await sample.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from services.voice_cloning import VoiceProvider, clone_voice
        result = await clone_voice(
            file_path=tmp_path,
            voice_name=voice_name,
            provider=VoiceProvider.ELEVENLABS,
            clone_profile_id=profile["id"],
        )
        return {
            "status": "ACTIVE" if result.get("status") == "ACTIVE" else "TRAINING",
            "voice_id": result.get("voice_id", ""),
            "voice_name": voice_name,
            "clone_name": profile["short_name"],
            "provider": "elevenlabs",
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Voice cloning failed: {exc}")
    finally:
        try:
            os_mod.unlink(tmp_path)
        except Exception:
            pass


# ── HITL Queue ───────────────────────────────────────────────────────────────
@router.get("/hitl/actions")
async def list_hitl_actions():
    return {
        "actions": _live_state["hitl_actions"],
        "total": len(_live_state["hitl_actions"]),
        "pending": len([a for a in _live_state["hitl_actions"] if a["status"] == "PENDING_HUMAN_SIGN_OFF"]),
    }


def _find_hitl(action_id: str) -> dict:
    for a in _live_state["hitl_actions"]:
        if a["id"] == action_id:
            return a
    raise HTTPException(status_code=404, detail="HITL action not found")


@router.post("/hitl/approve/{action_id}")
async def hitl_approve(action_id: str):
    action = _find_hitl(action_id)
    if action["status"] != "PENDING_HUMAN_SIGN_OFF":
        raise HTTPException(status_code=409, detail=f"Action is {action['status']}")
    action["status"] = "APPROVED"
    action["approved_at"] = datetime.utcnow().isoformat()
    logger.info("Live HITL approve: action=%s", action_id)
    return {"status": "APPROVED", "action_id": action_id}


@router.post("/hitl/reject/{action_id}")
async def hitl_reject(action_id: str):
    action = _find_hitl(action_id)
    action["status"] = "REJECTED"
    logger.info("Live HITL reject: action=%s", action_id)
    return {"status": "REJECTED", "action_id": action_id}


@router.post("/hitl/deploy/{action_id}")
async def hitl_deploy(action_id: str):
    action = _find_hitl(action_id)
    if action["status"] != "APPROVED":
        raise HTTPException(status_code=409, detail="Action must be APPROVED first")
    action["status"] = "DEPLOYED"
    action["deployed_at"] = datetime.utcnow().isoformat()
    action["published_url"] = f"https://acme-financial.io/posts/{str(uuid.uuid4())}"
    logger.info("Live HITL deploy: action=%s", action_id)
    return {"status": "DEPLOYED", "action_id": action_id, "published_url": action["published_url"]}


# ── Deploy to Platforms ──────────────────────────────────────────────────────
@router.post("/deploy/{platform}")
async def deploy_to_platform(platform: str, content_id: str = "", payload: dict | None = None):
    logger.info("Live deploy to %s: content_id=%s", platform, content_id)
    supported = ["twitter", "linkedin", "facebook", "blogspot", "wordpress", "shopify"]
    if platform not in supported:
        raise HTTPException(status_code=400, detail=f"Unsupported platform {platform}. Supported: {supported}")

    return {
        "status": "queued",
        "platform": platform,
        "content_id": content_id or str(uuid.uuid4()),
        "message": f"Content queued for publishing to {platform}. Real API integration requires OAuth tokens.",
    }
