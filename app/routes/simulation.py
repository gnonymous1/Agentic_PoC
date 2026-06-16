"""
Interactive simulation API endpoints for the browser-based dashboard.
Provides mock overnight tasks, clone chat, and Zoom meeting simulation.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.livekit_integration import generate_join_token
from app.services.real_meeting import RealMeetingSession
from app.services.recall_ai import RecallAIService, RecallSessionConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/simulate", tags=["Simulation"])

_sim_state: dict = {
    "overnight_tasks": [],
    "hitl_actions": [],
    "clone_conversations": {},
    "meeting_sessions": {},
    "client_id": str(uuid.uuid4()),
    "technical_twin_id": str(uuid.uuid4()),
    "sales_closer_id": str(uuid.uuid4()),
}

_CLONE_PROFILES = [
    {
        "id": _sim_state["technical_twin_id"],
        "slug": "technical_twin",
        "name": "Technical Twin — CTO Node",
        "short_name": "Technical Twin",
        "avatar": "👨‍💻",
        "color": "#3b82f6",
        "system_prompt": (
            "You are the CTO of Acme Financial Corp. You speak with deep "
            "technical authority on AI/ML infrastructure, cloud architecture, "
            "and financial data pipelines. You prefer precise, data-backed language."
        ),
        "voice_clone_id": "mock-voice-tech-twin-001",
        "guardrails": {"brand_tone": "technical_authoritative"},
    },
    {
        "id": _sim_state["sales_closer_id"],
        "slug": "sales_closer",
        "name": "Sales Closer — Revenue Node",
        "short_name": "Sales Closer",
        "avatar": "💼",
        "color": "#f59e0b",
        "system_prompt": (
            "You are the VP of Sales at Acme Financial Corp. You are "
            "persuasive, relationship-driven, and metrics-oriented. "
            "You speak in terms of ROI, TCO, and business outcomes."
        ),
        "voice_clone_id": "mock-voice-sales-close-002",
        "guardrails": {"brand_tone": "persuasive_consultative"},
    },
]

_CLONE_LOOKUP = {}
for _p in _CLONE_PROFILES:
    _CLONE_LOOKUP[_p["id"]] = _p
    _CLONE_LOOKUP[_p["slug"]] = _p


class ChatRequest(BaseModel):
    clone_id: str
    message: str
    conversation_id: str | None = None

class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    clone_name: str
    clone_avatar: str

class TaskResult(BaseModel):
    task_id: str
    status: str
    message: str
    hitl_action_id: str | None = None
    details: dict | None = None

class MeetingResult(BaseModel):
    session_id: str
    transcript: list[dict]
    deal_value: float | None = None
    hitl_action_id: str | None = None

class SimulationStatus(BaseModel):
    active_tasks: int
    pending_hitl: int
    total_hitl: int
    active_conversations: int
    active_meetings: int
    clones: list[dict]
    recent_tasks: list[dict]


async def _mock_research(topic: str) -> str:
    await asyncio.sleep(0.8)
    return (
        f"Unified Truth Document: {topic}\n\n"
        f"Analysis of {topic} reveals three critical trends for Q2-Q4 2026. "
        f"First, major financial institutions have increased AI infrastructure "
        f"spending by 47% year-over-year, with JP Morgan, Goldman Sachs, and "
        f"Morgan Stanley leading [source: financial-times.com]. "
        f"Second, regulatory frameworks are coalescing around the EU AI Act "
        f"and SEC disclosure requirements for AI-driven trading algorithms "
        f"[source: sec.gov]. "
        f"Third, the talent market for MLOps engineers specialized in financial "
        f"services has tightened, with salaries rising 32% [source: linkedin-worksplace-report].\n"
        f"[UNVERIFIED] Early projections suggest that by Q1 2027, over 60% of "
        f"retail banking interactions will be AI-mediated.\n"
        f"[source: mckinsey-financial-services-2026]"
    )

async def _mock_generate_content(utd: str) -> dict:
    await asyncio.sleep(0.5)
    return {
        "twitter": {"posts": [
            "Financial institutions just increased AI infrastructure spend by 47% YoY.",
            "JP Morgan is running 400+ AI models in production. The compliance framework is the secret sauce.",
            "EU AI Act + SEC disclosure rules for algo trading are reshaping compliance.",
            "MLOps engineer salaries in fintech just jumped 32%.",
            "By 2027, 60%+ of retail banking interactions will be AI-mediated.",
            "Institutional AI adoption is not coming. It is here.",
            "Drop a follow for our Q2 benchmarks in regulated environments.",
        ]},
        "linkedin": {
            "body": "The enterprise AI landscape in financial services just shifted.\n\n• 47% YoY increase in AI infra spend\n• 400+ production models at a single institution\n• 32% salary surge for MLOps engineers\n\nThe real competitive advantage is compliance automation.",
            "hashtags": ["#FinancialServices", "#AIEngineering", "#MLOps"],
        },
        "facebook": {
            "body": "47% more infrastructure spend. 400+ models in production. MLOps salaries jumping 32%.\n\nWhat is your institution doing about AI governance?",
            "call_to_action": "Share your approach below.",
        },
        "blogspot": {
            "title": "Enterprise AI in Financial Services: The 2026 Reality",
            "seo_slug": "enterprise-ai-financial-services-2026",
            "meta_description": "Deep analysis of AI infrastructure trends in financial services for 2026.",
            "html_body": (
                "<h2>The State of Financial AI in 2026</h2>"
                "<p>The financial services sector has crossed a critical "
                "threshold in 2026. Institutional AI adoption has moved "
                "firmly into production at scale.</p>"
                "<h3>Infrastructure Investment Surge</h3>"
                "<p>The top 20 global banks spent over $47 billion on AI "
                "infrastructure in 2025, a 47% increase year-over-year.</p>"
                "<h3>Regulatory Evolution</h3>"
                "<p>The EU AI Act and SEC disclosure requirements for "
                "AI-driven trading algorithms are reshaping compliance.</p>"
                "<h3>Talent Market</h3>"
                "<p>MLOps engineers with financial services experience have "
                "seen a 32% salary increase over the past 12 months.</p>"
                "<h3>Looking Ahead</h3>"
                "<p>McKinsey projects over 60% of retail banking interactions "
                "will be AI-mediated by Q1 2027.</p>"
            ),
        },
    }

_MEETING_SCRIPT = [
    {"speaker": "system",     "text": "🔗 LiveKit WebRTC connection established. Audio codec: Opus 48kHz.",                                              "delay": 0.5},
    {"speaker": "system",     "text": "📹 Recall.ai bot joined the meeting room. Screen capture active.",                                              "delay": 0.8},
    {"speaker": "customer",   "text": "Hey, thanks for taking this call. We are evaluating enterprise AI platforms for our risk management pipeline.", "delay": 1.5},
    {"speaker": "clone",      "text": "Chris, glad we could make this work. Before we dive into the technical architecture — what is your timeline and what compliance framework are you operating under?", "delay": 2.5},
    {"speaker": "customer",   "text": "We need to be live in Q3. We operate under SEC guidelines and we are prepping for EU AI Act compliance.", "delay": 1.5},
    {"speaker": "clone",      "text": "That timeline is aggressive but doable. Our platform already has the SEC disclosure framework baked in and we are SOC 2 Type II certified. Can I share a proposed architecture and pricing ballpark this week?", "delay": 2.5},
    {"speaker": "customer",   "text": "Yes, please. That would be helpful. What does your typical deployment look like?", "delay": 1.5},
    {"speaker": "clone",      "text": "Great question. Our standard deployment is a 6-week phased rollout: week 1-2 discovery and environment setup, week 3-4 integration and configuration, week 5-6 testing and go-live. We have done this 40+ times.", "delay": 3.0},
    {"speaker": "customer",   "text": "That timeline works for us. What about pricing?", "delay": 1.2},
    {"speaker": "clone",      "text": "For your scale — enterprise risk management pipeline, approximately 500K transactions per day — our standard engagement is $250K ACV with a 12-month term. This includes full platform access, dedicated support, and compliance engineering hours.", "delay": 3.5},
    {"speaker": "customer",   "text": "That is within our budget. Can we move forward?", "delay": 1.0},
    {"speaker": "system",     "text": "🤖 Buying signal detected — confidence 94%",                                                                    "delay": 0.5},
    {"speaker": "system",     "text": "💰 Deal: $250,000 ACV | Term: 12 months | Customer: FinTechX",                                                  "delay": 0.5},
    {"speaker": "system",     "text": "📋 Contract proposal queued for HITL approval",                                                                 "delay": 0.3},
    {"speaker": "system",     "text": "📊 Deal stage: discovery → negotiation | CRM updated",                                                          "delay": 0.3},
    {"speaker": "clone",      "text": "Excellent. I will have the proposal on your desk by end of day. Looking forward to building this together.",     "delay": 1.5},
    {"speaker": "system",     "text": "✅ Meeting complete — $250K opportunity in pipeline",                                                            "delay": 0.0},
]


def _resolve_clone(clone_id: str) -> dict:
    profile = _CLONE_LOOKUP.get(clone_id)
    if profile:
        return profile
    for p in _CLONE_PROFILES:
        if p["id"] == clone_id or p["slug"] == clone_id:
            return p
        if clone_id in p["name"].lower():
            return p
    raise HTTPException(status_code=404, detail=f"Clone not found: {clone_id}")


@router.get("/status", response_model=SimulationStatus)
async def get_status():
    pending = len([a for a in _sim_state["hitl_actions"] if a["status"] == "PENDING_HUMAN_SIGN_OFF"])
    return SimulationStatus(
        active_tasks=len(_sim_state["overnight_tasks"]),
        pending_hitl=pending,
        total_hitl=len(_sim_state["hitl_actions"]),
        active_conversations=len(_sim_state["clone_conversations"]),
        active_meetings=len(_sim_state["meeting_sessions"]),
        clones=_CLONE_PROFILES,
        recent_tasks=_sim_state["overnight_tasks"][-5:],
    )


@router.post("/overnight-task", response_model=TaskResult)
async def run_overnight_task(
    topic: str = "Enterprise AI Adoption Trends in Financial Services 2026",
    clone_id: str | None = None,
):
    task_id = str(uuid.uuid4())
    profile = _resolve_clone(clone_id) if clone_id else _CLONE_PROFILES[0]
    logger.info("Overnight task %s | clone=%s topic=%s", task_id, profile["slug"], topic[:50])

    _sim_state["overnight_tasks"].append({
        "id": task_id, "topic": topic, "status": "RUNNING",
        "started_at": datetime.utcnow().isoformat(),
    })

    try:
        utd = await _mock_research(topic)
        content = await _mock_generate_content(utd)
        hitl_id = str(uuid.uuid4())
        _sim_state["hitl_actions"].append({
            "id": hitl_id,
            "action_type": "content_publish",
            "status": "PENDING_HUMAN_SIGN_OFF",
            "payload": content,
            "clone_id": profile["slug"],
            "clone_name": profile["short_name"],
            "utd_summary": utd[:200],
            "created_at": datetime.utcnow().isoformat(),
        })
        t = next((t for t in _sim_state["overnight_tasks"] if t["id"] == task_id), None)
        if t:
            t["status"] = "COMPLETED"
            t["hitl_action_id"] = hitl_id

        return TaskResult(
            task_id=task_id, status="COMPLETED",
            message="Content generated and queued for human approval",
            hitl_action_id=hitl_id,
            details={"utd_word_count": len(utd.split()), "platforms": list(content.keys()), "topic": topic},
        )
    except Exception as exc:
        logger.error("Overnight task failed: %s", exc)
        t = next((t for t in _sim_state["overnight_tasks"] if t["id"] == task_id), None)
        if t: t["status"] = "FAILED"
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clone-chat", response_model=ChatResponse)
async def clone_chat(req: ChatRequest):
    profile = _resolve_clone(req.clone_id)

    conv_id = req.conversation_id or str(uuid.uuid4())
    if conv_id not in _sim_state["clone_conversations"]:
        _sim_state["clone_conversations"][conv_id] = {
            "clone_id": profile["slug"],
            "clone_name": profile["short_name"],
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
        }

    _sim_state["clone_conversations"][conv_id]["messages"].append({
        "role": "user", "content": req.message,
        "timestamp": datetime.utcnow().isoformat(),
    })

    await asyncio.sleep(0.6)

    tone = profile["guardrails"].get("brand_tone", "professional")
    name = profile["short_name"]

    replies = {
        "hello": f"Hello! I am {name}. How can I help you today?",
        "hi": f"Hi there. {name} here. What is on your mind?",
        "who are you": f"I am {name}, a digital clone operating inside the Sovereign Executive Proxy Engine. I handle communications and decisions on behalf of my executive counterpart.",
        "help": "Of course. I can generate content, respond to inquiries, draft proposals, and join meetings on your behalf. What would you like me to take care of?",
        "ok here i will do": "Understood. I am on it. I will generate the content, route it through the critic for quality assurance, and queue it for your approval. You will see it in the HITL queue shortly.",
    }

    msg_lower = req.message.lower().strip()
    matched = None
    for key, reply in replies.items():
        if key in msg_lower:
            matched = reply
            break

    if not matched:
        matched = (
            "Thank you for that question. Based on my analysis and the current market data, "
            "I recommend we approach this by first establishing a clear baseline and then "
            "iterating based on measurable outcomes. Our platform has been deployed across "
            "similar environments with a median time-to-value of 6 weeks. "
            "Should I prepare a detailed proposal for your review?"
        )

    _sim_state["clone_conversations"][conv_id]["messages"].append({
        "role": "assistant", "content": matched,
        "timestamp": datetime.utcnow().isoformat(),
    })

    return ChatResponse(
        conversation_id=conv_id,
        reply=matched,
        clone_name=profile["short_name"],
        clone_avatar=profile["avatar"],
    )


@router.get("/clone-chat/{conversation_id}")
async def get_conversation(conversation_id: str):
    conv = _sim_state["clone_conversations"].get(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/zoom-meeting", response_model=MeetingResult)
async def simulate_zoom_meeting():
    # If Recall.ai is configured, spawn a real headless meeting bot and return its session/transcript.
    if settings.recall_ai_api_key:
        recall = RecallAIService()
        meeting_url = "https://zoom.us/j/000000000"  # In production, accept meeting URL param from client
        cfg = RecallSessionConfig(meeting_url=meeting_url, platform="zoom", recording_mode="audio_video", duration_minutes=30)
        try:
            session = await recall.create_session(cfg)
            # attempt to fetch transcript (may be streaming/async); try a short poll loop
            transcript = None
            for _ in range(10):
                await asyncio.sleep(2)
                try:
                    transcript = await recall.get_transcript(session.session_id)
                    if transcript:
                        break
                except Exception:
                    continue

            session_id = session.session_id
            hitl_id = str(uuid.uuid4())
            _sim_state["hitl_actions"].append({
                "id": hitl_id,
                "action_type": "proposal_generation",
                "status": "PENDING_HUMAN_SIGN_OFF",
                "payload": {"deal_value": 250000, "contract_term_months": 12, "customer": "FinTechX"},
                "clone_id": "sales_closer",
                "clone_name": "Sales Closer",
                "meeting_session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
            })

            _sim_state["meeting_sessions"][session_id] = {
                "transcript": transcript or _MEETING_SCRIPT,
                "deal_value": 250000,
                "hitl_action_id": hitl_id,
                "status": "COMPLETED" if transcript else "COMPLETED (simulated)",
                "created_at": datetime.utcnow().isoformat(),
            }

            return MeetingResult(
                session_id=session_id,
                transcript=_sim_state["meeting_sessions"][session_id]["transcript"],
                deal_value=250000,
                hitl_action_id=hitl_id,
            )
        except Exception as exc:
            logger.warning("Recall.ai meeting spawn failed, falling back to simulated script: %s", exc)

    # Fallback: use scripted meeting transcript (existing behaviour)
    session_id = str(uuid.uuid4())

    hitl_id = str(uuid.uuid4())
    _sim_state["hitl_actions"].append({
        "id": hitl_id,
        "action_type": "proposal_generation",
        "status": "PENDING_HUMAN_SIGN_OFF",
        "payload": {"deal_value": 250000, "contract_term_months": 12, "customer": "FinTechX"},
        "clone_id": "sales_closer",
        "clone_name": "Sales Closer",
        "meeting_session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
    })

    _sim_state["meeting_sessions"][session_id] = {
        "transcript": _MEETING_SCRIPT,
        "deal_value": 250000,
        "hitl_action_id": hitl_id,
        "status": "COMPLETED",
        "created_at": datetime.utcnow().isoformat(),
    }

    return MeetingResult(
        session_id=session_id,
        transcript=_MEETING_SCRIPT,
        deal_value=250000,
        hitl_action_id=hitl_id,
    )


@router.post("/real-meeting/start")
async def start_real_meeting(room_name: str = "acme-sales-001"):
    """Initiate a real-time WebRTC meeting with Gemini Live integration (prototype)."""
    session_id = str(uuid.uuid4())
    client_id = _sim_state["client_id"]
    agent_profile = _CLONE_PROFILES[1]  # Sales Closer

    # Generate LiveKit tokens
    lk_tokens = generate_join_token(agent_profile["slug"], room_name)

    # Create real meeting session
    session = RealMeetingSession(
        session_id=session_id,
        client_id=client_id,
        agent_profile_id=agent_profile["id"],
        livekit_room=room_name,
        livekit_token=lk_tokens["token"],
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        agent_prompt=agent_profile["system_prompt"],
        voice_model_id=agent_profile.get("voice_clone_id"),
    )

    _sim_state["meeting_sessions"][session_id] = {
        "session_obj": session,
        "livekit_url": lk_tokens["url"],
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }

    result = await session.start_session()
    result["livekit_url"] = lk_tokens["url"]
    result["livekit_token"] = lk_tokens["token"]
    result["room_name"] = room_name

    return result


@router.post("/real-meeting/{session_id}/end")
async def end_real_meeting(session_id: str):
    """Gracefully end a real meeting session."""
    meet_data = _sim_state["meeting_sessions"].get(session_id)
    if not meet_data:
        raise HTTPException(status_code=404, detail="Meeting session not found")

    session_obj = meet_data.get("session_obj")
    if not session_obj:
        raise HTTPException(status_code=400, detail="Not a real meeting session")

    result = await session_obj.end_session()
    meet_data["status"] = "ended"
    meet_data["ended_at"] = datetime.utcnow().isoformat()
    meet_data["transcript"] = session_obj.transcript_lines

    return result


@router.get("/real-meeting/{session_id}/status")
async def get_real_meeting_status(session_id: str):
    """Poll status of an active real meeting."""
    meet_data = _sim_state["meeting_sessions"].get(session_id)
    if not meet_data:
        raise HTTPException(status_code=404, detail="Meeting session not found")

    session_obj = meet_data.get("session_obj")
    if not session_obj:
        raise HTTPException(status_code=400, detail="Not a real meeting session")

    return {
        "session_id": session_id,
        "status": "active" if session_obj.is_active else "inactive",
        "transcript_lines": len(session_obj.transcript_lines),
        "tool_calls": len(session_obj.tool_calls_executed),
        "room_name": session_obj.livekit_room,
    }


@router.get("/zoom-meeting/{session_id}")
async def get_meeting(session_id: str):
    session = _sim_state["meeting_sessions"].get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Meeting session not found")
    return session


@router.post("/hitl/approve/{action_id}")
async def approve_hitl(action_id: str):
    action = next((a for a in _sim_state["hitl_actions"] if a["id"] == action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail="HITL action not found")
    if action["status"] != "PENDING_HUMAN_SIGN_OFF":
        raise HTTPException(status_code=409, detail=f"Action is {action['status']}")
    action["status"] = "APPROVED"
    action["approved_at"] = datetime.utcnow().isoformat()
    return {"status": "APPROVED", "action_id": action_id}


@router.post("/hitl/reject/{action_id}")
async def reject_hitl(action_id: str):
    action = next((a for a in _sim_state["hitl_actions"] if a["id"] == action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail="HITL action not found")
    action["status"] = "REJECTED"
    return {"status": "REJECTED", "action_id": action_id}


@router.post("/hitl/deploy/{action_id}")
async def deploy_hitl(action_id: str):
    action = next((a for a in _sim_state["hitl_actions"] if a["id"] == action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail="HITL action not found")
    if action["status"] != "APPROVED":
        raise HTTPException(status_code=409, detail="Action must be APPROVED first")
    action["status"] = "DEPLOYED"
    action["deployed_at"] = datetime.utcnow().isoformat()
    action["deployed_response"] = {
        "platform_response": "HTTP 200",
        "content_id": str(uuid.uuid4()),
        "published_url": f"https://acme-financial.io/posts/{uuid.uuid4()}",
    }
    return {"status": "DEPLOYED", "action_id": action_id, "published_url": action["deployed_response"]["published_url"]}


@router.get("/hitl/actions")
async def list_hitl_actions():
    return {
        "actions": _sim_state["hitl_actions"],
        "total": len(_sim_state["hitl_actions"]),
        "pending": len([a for a in _sim_state["hitl_actions"] if a["status"] == "PENDING_HUMAN_SIGN_OFF"]),
    }


@router.post("/reset")
async def reset_simulation():
    _sim_state["overnight_tasks"].clear()
    _sim_state["hitl_actions"].clear()
    _sim_state["clone_conversations"].clear()
    _sim_state["meeting_sessions"].clear()
    return {"status": "RESET", "message": "Simulation state cleared"}
