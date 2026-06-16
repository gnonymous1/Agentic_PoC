"""
GNONE — Unified Pydantic Schemas.
Strongly typed data contracts for all system components.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ===========================================================================
# DAG SCHEMAS
# ===========================================================================

class DagNodeSchema(BaseModel):
    node_id: str = Field(..., description="Unique task identifier, e.g. TASK_001")
    depends_on: List[str] = Field(default=[], description="Prerequisite node_ids")
    agent_skill: str = Field(..., description="Target skill/module")
    input_parameters: Dict[str, Any] = Field(default={}, description="Skill arguments")
    requires_human_approval: bool = Field(default=False, description="HITL gate flag")
    status: str = Field(default="pending", description="pending|running|completed|failed|pending_approval")
    telemetry: Optional[str] = Field(default="", description="Diagnostic output")


class DagLayerSchema(BaseModel):
    layer_id: int
    nodes: List[DagNodeSchema]


class AutonomousDagSchema(BaseModel):
    macro_goal: str
    dag_layers: List[DagLayerSchema]


# ===========================================================================
# CONTENT SCHEMAS
# ===========================================================================

class TwitterContent(BaseModel):
    posts: List[str] = Field(..., description="Thread of 5-10 posts, each under 240 chars")


class LinkedInContent(BaseModel):
    body: str = Field(..., description="Analytical corporate post")
    hashtags: List[str] = Field(default=[], description="Hashtags")


class BlogspotContent(BaseModel):
    title: str = Field(..., description="SEO-optimized article title")
    html_body: str = Field(..., description="Semantic HTML5 article, min 600 words")


class MultiPlatformPayload(BaseModel):
    twitter: TwitterContent
    linkedin: LinkedInContent
    blogspot: BlogspotContent


# ===========================================================================
# HITL SCHEMAS
# ===========================================================================

class HitlActionRequest(BaseModel):
    ledger_id: str = Field(..., description="ContentStateLedger UUID")
    action: str = Field(..., description="APPROVE, REJECT, or REWRITE")
    notes: Optional[str] = Field(None, description="Feedback for REWRITE")
    topic: Optional[str] = Field(None, description="Research topic for regeneration")
    persona_prompt: Optional[str] = Field(None, description="Persona system instructions")


class HitlActionResponse(BaseModel):
    ledger_id: str
    action_executed: str
    status: str
    timestamp: str
    dispatch_results: Optional[Dict[str, Any]] = None
    rewrite_ledger_id: Optional[str] = None


# ===========================================================================
# API REQUEST SCHEMAS
# ===========================================================================

class DagCompileRequest(BaseModel):
    macro_goal: str


class MeetingBriefRequest(BaseModel):
    meeting_title: str
    stakeholders: str
    calendar_link: Optional[str] = None


class FinancialEntryRequest(BaseModel):
    title: str
    amount: float
    entry_type: str  # payable|receivable|expense
    source_document: Optional[str] = None
