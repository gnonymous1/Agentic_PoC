"""
SEPE — Sovereign Executive Proxy Engine
Production Human-in-the-Loop (HITL) State Transition Gateway

This module provides the FastAPI endpoints for executive content reviews.
On APPROVE, the system decrypts credentials using AES-256-GCM and dispatches:
  - Meta Graph API (LinkedIn / Facebook pages)
  - X API v2 (Twitter threads)
  - Google Blogger REST API (long-form HTML5 articles)
On REWRITE, feedback notes trigger immediate self-healing copywriting runs.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx

from database_models import get_db_session, ContentStateLedger, OAuthVault, Account, PersonaRegistry
from content_engine import ContentFactoryEngine, MultiPlatformPayload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/hitl", tags=["Human-in-the-Loop"])

# ===========================================================================
# 1. AES-256-GCM DECRYPTION HELPER
# ===========================================================================

def decrypt_vault_credential(encrypted_token: bytes, iv: bytes, tag: bytes) -> str:
    """
    Decrypts long-lived channel access tokens strictly in memory using AES-256-GCM.
    Enforces master key length checks.
    """
    key_hex = os.getenv("SEPE_MASTER_KEY")
    if not key_hex:
        raise ValueError("PRODUCTION CRYPTO EXCLUSION: 'SEPE_MASTER_KEY' env variable must be set for Vault decryption.")
        
    try:
        key_bytes = bytes.fromhex(key_hex)
    except ValueError:
        raise ValueError("PRODUCTION CRYPTO EXCLUSION: 'SEPE_MASTER_KEY' is not a valid hex string.")
        
    if len(key_bytes) != 32:
        raise ValueError("PRODUCTION CRYPTO EXCLUSION: 'SEPE_MASTER_KEY' must be exactly 32 bytes (64 hex characters).")
        
    aesgcm = AESGCM(key_bytes)
    # Reconstruct the combined ciphertext + tag representation for standard GCM decryptor
    ciphertext = encrypted_token + tag
    
    try:
        decrypted_bytes = aesgcm.decrypt(iv, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
    except Exception as exc:
        logger.error("AES-256-GCM Decryption failure: %s", exc)
        raise ValueError(f"Decryption boundary compromised. Master key mismatch or data corrupted: {exc}")


# ===========================================================================
# 2. TRANSITION GATEWAY MODELS
# ===========================================================================

class HitlActionRequest(BaseModel):
    ledger_id: str = Field(..., description="The unique UUID of the ContentStateLedger draft.")
    action: str = Field(..., description="Action argument: APPROVE, REJECT, or REWRITE.")
    notes: Optional[str] = Field(None, description="Optional feedback or critique notes required for REWRITE.")
    
    # Context parameters required to re-run the Content Engine
    topic: Optional[str] = Field(None, description="The research topic target for the regeneration cycle.")
    persona_prompt: Optional[str] = Field(None, description="System instructions representing the executive persona.")


class HitlActionResponse(BaseModel):
    ledger_id: str
    action_executed: str
    status: str
    timestamp: str
    dispatch_results: Optional[Dict[str, Any]] = None
    rewrite_ledger_id: Optional[str] = None


# ===========================================================================
# 3. DIRECT PLATFORM CONCURRENT REST PUBLISHERS
# ===========================================================================

async def dispatch_to_meta(token: str, body: str) -> Dict[str, Any]:
    """
    Publishes analytical B2B copy to the Meta Graph API gateway.
    """
    logger.info("Executing real Meta Graph API concurrent worker dispatch...")
    url = "https://graph.facebook.com/v19.0/me/feed"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                url,
                json={"message": body, "access_token": token}
            )
            resp.raise_for_status()
            logger.info("Successfully posted to Meta Graph API.")
            return {"platform": "meta", "status": "success", "response": resp.json()}
        except Exception as exc:
            logger.error("Meta Graph API worker failed: %s", exc)
            return {"platform": "meta", "status": "failed", "error": str(exc)}


async def dispatch_to_x(token: str, posts: List[str]) -> Dict[str, Any]:
    """
    Publishes an structured thread of posts to the X API v2 endpoint.
    """
    logger.info("Executing real X API v2 concurrent thread dispatcher...")
    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=20.0) as client:
        responses = []
        try:
            for i, post in enumerate(posts):
                logger.info("Publishing Tweet %d/%d to X...", i+1, len(posts))
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"text": post}
                )
                resp.raise_for_status()
                responses.append(resp.json())
            logger.info("Successfully posted thread to X API.")
            return {"platform": "x", "status": "success", "responses": responses}
        except Exception as exc:
            logger.error("X API v2 thread worker failed: %s", exc)
            return {"platform": "x", "status": "failed", "error": str(exc)}


async def dispatch_to_blogspot(token: str, title: str, html_body: str) -> Dict[str, Any]:
    """
    Publishes comprehensive long-form semantic HTML articles to the Google Blogger REST API.
    """
    logger.info("Executing real Google Blogger REST API concurrent publisher...")
    blog_id = os.getenv("GOOGLE_BLOGGER_BLOG_ID", "default")
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts"
    headers = {
        "Authorization": f"Bearer {token}", 
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                url,
                headers=headers,
                json={
                    "kind": "blogger#post",
                    "title": title,
                    "content": html_body
                }
            )
            resp.raise_for_status()
            logger.info("Successfully posted to Google Blogger API.")
            return {"platform": "blogspot", "status": "success", "response": resp.json()}
        except Exception as exc:
            logger.error("Google Blogger API worker failed: %s", exc)
            return {"platform": "blogspot", "status": "failed", "error": str(exc)}


# ===========================================================================
# 4. FastAPI HITL GATEWAY CONTROLLER
# ===========================================================================

@router.post("/action", response_model=HitlActionResponse)
async def execute_hitl_transition(
    req: HitlActionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Orchestrates approval, rejection, or self-healing rewrite transitions on content assets.
    """
    logger.info("HITL Gateway: processing action '%s' for ledger_id=%s", req.action.upper(), req.ledger_id)
    
    # 1. Fetch Ledger Record
    try:
        ledger_uuid = uuid.UUID(req.ledger_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed ledger UUID string.")
        
    stmt = select(ContentStateLedger).where(ContentStateLedger.id == ledger_uuid)
    res = await db.execute(stmt)
    ledger_item = res.scalar_one_or_none()
    
    if not ledger_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"ContentStateLedger entry '{req.ledger_id}' not found."
        )
        
    # Check execution boundaries
    if ledger_item.status != "PENDING_HUMAN_SIGN_OFF" and req.action.upper() != "REWRITE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Content draft has already progressed out of sign-off state. Current status: '{ledger_item.status}'"
        )

    action_target = req.action.upper()
    now_str = datetime.utcnow().isoformat()

    # =======================================================================
    # CASE A: APPROVAL & CONCURRENT REST DEPLOYMENT
    # =======================================================================
    if action_target == "APPROVE":
        logger.info("Transitioning ledger status: PENDING_HUMAN_SIGN_OFF -> APPROVED")
        ledger_item.status = "APPROVED"
        ledger_item.approved_at = datetime.utcnow()
        await db.flush()

        # Decrypt access tokens from the secure OAuth Vault
        vault_stmt = select(OAuthVault).where(OAuthVault.account_id == ledger_item.account_id)
        vault_res = await db.execute(vault_stmt)
        vault_entries = vault_res.scalars().all()

        tokens = {}
        for entry in vault_entries:
            try:
                decrypted = decrypt_vault_credential(
                    encrypted_token=entry.encrypted_token,
                    iv=entry.encrypted_iv,
                    tag=entry.encrypted_tag
                )
                tokens[entry.platform] = decrypted
            except Exception as exc:
                logger.error("Failed to decrypt credentials for platform %s: %s", entry.platform, exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Cryptographic Vault decryption failure on platform '{entry.platform}'"
                )

        # Enforce scope check requirements
        for platform in ["meta", "x", "blogspot"]:
            if platform not in tokens:
                raise HTTPException(
                    status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                    detail=f"Missing active, decrypted token for target platform: '{platform}' inside secure vault."
                )

        # Parse generated layout payload from state ledger
        try:
            payload_dict = json.loads(ledger_item.payload)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ledger payload content is not valid JSON."
            )

        # Launch Exception-Shielded Concurrent Dispatches
        logger.info("Initiating concurrent API dispatches...")
        
        meta_payload = payload_dict.get("linkedin", {})
        twitter_payload = payload_dict.get("twitter", {})
        blogspot_payload = payload_dict.get("blogspot", {})

        meta_task = dispatch_to_meta(tokens["meta"], meta_payload.get("body", ""))
        x_task = dispatch_to_x(tokens["x"], twitter_payload.get("posts", []))
        blogspot_task = dispatch_to_blogspot(
            tokens["blogspot"], blogspot_payload.get("title", ""), blogspot_payload.get("html_body", "")
        )

        # GATHER RESULTS (return_exceptions=True protects parallel execution channels)
        results = await asyncio.gather(meta_task, x_task, blogspot_task, return_exceptions=True)

        dispatch_summary = {}
        all_success = True
        
        for idx, platform in enumerate(["meta", "x", "blogspot"]):
            res_val = results[idx]
            if isinstance(res_val, Exception):
                logger.error("Platform '%s' dispatch raised code exception: %s", platform, res_val)
                dispatch_summary[platform] = {"status": "failed", "error": str(res_val)}
                all_success = False
            else:
                dispatch_summary[platform] = res_val
                if res_val.get("status") == "failed":
                    all_success = False

        if all_success:
            ledger_item.status = "DEPLOYED"
            ledger_item.deployed_at = datetime.utcnow()
            logger.info("Ledger id=%s successfully DEPLOYED across all active platforms.", ledger_item.id)
        else:
            ledger_item.status = "FAILED"
            logger.error("Ledger id=%s failed deployment checks on certain platforms.", ledger_item.id)

        await db.commit()
        return HitlActionResponse(
            ledger_id=str(ledger_item.id),
            action_executed="APPROVE",
            status=ledger_item.status,
            timestamp=now_str,
            dispatch_results=dispatch_summary
        )

    # =======================================================================
    # CASE B: REJECTION
    # =======================================================================
    elif action_target == "REJECT":
        logger.info("Transitioning ledger status: PENDING_HUMAN_SIGN_OFF -> REJECTED")
        ledger_item.status = "REJECTED"
        ledger_item.refinement_notes = req.notes or "Rejected by human administrator."
        await db.commit()

        return HitlActionResponse(
            ledger_id=str(ledger_item.id),
            action_executed="REJECT",
            status="REJECTED",
            timestamp=now_str
        )

    # =======================================================================
    # CASE C: SELF-HEALING REWRITE LOOP
    # =======================================================================
    elif action_target == "REWRITE":
        logger.info("Executing immediate auto-healed rewrite loop...")
        
        if not req.notes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom feedback notes are required to execute a REWRITE action."
            )
            
        topic = req.topic or "Enterprise AI Infrastructure Compliance"
        persona_prompt = req.persona_prompt or "You are a professional corporate executive."

        gemini_key = os.getenv("GEMINI_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")

        engine = ContentFactoryEngine(gemini_key=gemini_key, openrouter_key=openrouter_key)
        
        try:
            # Rerun complete fact grounding and generative rewrite cycles with the user notes injected
            new_payload, _, success = await engine.execute_publishing_pipeline(
                topic=topic,
                persona_prompt=f"{persona_prompt}\n\nHuman Revision Request: {req.notes}",
                max_healing_turns=3
            )
        except Exception as exc:
            logger.error("Self-healing rewrite engine loop crashed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Self-healing rewrite cycle failed: {exc}"
            )

        # Create new child ContentStateLedger draft
        new_ledger = ContentStateLedger(
            account_id=ledger_item.account_id,
            persona_id=ledger_item.persona_id,
            action_type="content_publish",
            status="PENDING_HUMAN_SIGN_OFF",
            payload=json.dumps(new_payload.model_dump()),
            refinement_notes=f"Auto-healed from original draft '{req.ledger_id}' using notes: {req.notes}",
            original_action_id=ledger_item.id
        )

        db.add(new_ledger)
        await db.flush()
        
        # Mark parent ledger status as REJECTED to denote it has been superceded
        ledger_item.status = "REJECTED"
        ledger_item.refinement_notes = f"Superceded by child rewrite draft '{new_ledger.id}'"
        
        await db.commit()
        logger.info("Successfully generated rewrite draft '%s' referencing original '%s'", new_ledger.id, ledger_item.id)

        return HitlActionResponse(
            ledger_id=str(ledger_item.id),
            action_executed="REWRITE",
            status="REJECTED",
            timestamp=now_str,
            rewrite_ledger_id=str(new_ledger.id)
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action argument '{req.action}'. Allowed values: APPROVE, REJECT, REWRITE."
        )


# ===========================================================================
# 5. NEW DC-MO DAG AND PORTFOLIO ROUTERS
# ===========================================================================

class DagCompileRequest(BaseModel):
    macro_goal: str

@router.post("/dag/compile")
async def compile_and_run_dag(req: DagCompileRequest, db: AsyncSession = Depends(get_db_session)):
    from dag_orchestrator import DagOrchestratorEngine
    # 1. Fetch organizational account
    stmt = select(Account)
    res = await db.execute(stmt)
    account = res.scalars().first()
    if not account:
        account = Account(org_name="Executive Org", org_slug="executive-org", billing_email="billing@exec.com")
        db.add(account)
        await db.flush()

    engine = DagOrchestratorEngine(db_session=db)
    dag_obj = await engine.compile_macro_goal_to_dag(req.macro_goal)
    ledger_id = await engine.register_dag_in_ledger(dag_obj, account.id)
    
    # Run execution pipeline in the background asynchronously
    asyncio.create_task(engine.execute_dag_pipeline(ledger_id))
    return {"status": "running", "ledger_id": str(ledger_id), "dag": dag_obj.model_dump()}

@router.get("/dag/active")
async def get_active_dags(db: AsyncSession = Depends(get_db_session)):
    from database_models import DagExecutionLedger
    stmt = select(DagExecutionLedger).order_by(DagExecutionLedger.created_at.desc())
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        {
            "id": str(x.id),
            "macro_goal": x.macro_goal,
            "status": x.status,
            "dag_json": x.dag_json,
            "telemetry_logs": x.telemetry_logs,
            "created_at": x.created_at.isoformat()
        } for x in items
    ]

@router.post("/dag/release")
async def release_dag_gate(payload: Dict[str, str], db: AsyncSession = Depends(get_db_session)):
    from dag_orchestrator import DagOrchestratorEngine
    ledger_id_str = payload.get("ledger_id")
    if not ledger_id_str:
        raise HTTPException(status_code=400, detail="ledger_id is required.")
    
    engine = DagOrchestratorEngine(db_session=db)
    await engine.release_human_approval_gate(uuid.UUID(ledger_id_str))
    return {"status": "gate_released"}

@router.get("/drafts/pending")
async def get_pending_drafts(db: AsyncSession = Depends(get_db_session)):
    stmt = select(ContentStateLedger).where(ContentStateLedger.status == "PENDING_HUMAN_SIGN_OFF")
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        {
            "id": str(x.id),
            "payload": x.payload,
            "created_at": x.created_at.isoformat()
        } for x in items
    ]

@router.get("/financial/ledgers")
async def get_financial_ledgers(db: AsyncSession = Depends(get_db_session)):
    from database_models import FinancialLedger
    stmt = select(FinancialLedger).order_by(FinancialLedger.created_at.desc())
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        {
            "title": x.title,
            "amount": float(x.amount),
            "entry_type": x.entry_type,
            "status": x.status,
            "created_at": x.created_at.isoformat()
        } for x in items
    ]

@router.get("/workspace/documents")
async def get_workspace_documents(db: AsyncSession = Depends(get_db_session)):
    from database_models import WorkspaceDocument
    stmt = select(WorkspaceDocument).order_by(WorkspaceDocument.created_at.desc())
    res = await db.execute(stmt)
    items = res.scalars().all()
    return [
        {
            "filename": x.filename,
            "file_type": x.file_type,
            "summary": x.summary,
            "vector_status": x.vector_status,
            "created_at": x.created_at.isoformat()
        } for x in items
    ]

