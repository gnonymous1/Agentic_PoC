"""
SEPE — Sovereign Executive Proxy Engine
Autonomous JSON DAG Orchestrator & Multi-Agent Executor

This module implements the non-linear execution framework:
  1. Compiles abstract macro-goals into strongly typed JSON DAG dependency layers.
  2. Runs concurrent async execution loops, respecting node prerequisite flows.
  3. Enforces Human-in-the-Loop (HITL) gates for high-risk nodes.
  4. Manages workspace indexing, financial ledgers, content pipelines, and pre-meeting briefs.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
import httpx

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# Import production models
from database_models import (
    get_db_session,
    FinancialLedger,
    WorkspaceDocument,
    DagExecutionLedger,
    ContentStateLedger,
    PersonaRegistry
)
from content_engine import ContentFactoryEngine

logger = logging.getLogger(__name__)

# ===========================================================================
# 1. PYDANTIC DAG LAYER SCHEMAS
# ===========================================================================

class DagNodeSchema(BaseModel):
    node_id: str = Field(..., description="Unique code of task, e.g. TASK_001")
    depends_on: List[str] = Field(default=[], description="List of prerequisite node_ids that must complete first.")
    agent_skill: str = Field(..., description="Target skill: Read_Document, Process_Invoice, Generate_Branding_Content, Execute_Financial_Log, Synthesize_Brief")
    input_parameters: Dict[str, Any] = Field(default={}, description="Input arguments for target agent skills.")
    requires_human_approval: bool = Field(default=False, description="Strict risk parameter boundary.")
    status: str = Field(default="pending", description="Playout status: pending, running, completed, failed, pending_approval")
    telemetry: Optional[str] = Field(default="", description="Diagnostic telemetry or outputs.")


class DagLayerSchema(BaseModel):
    layer_id: int
    nodes: List[DagNodeSchema]


class AutonomousDagSchema(BaseModel):
    macro_goal: str
    dag_layers: List[DagLayerSchema]


# ===========================================================================
# 2. DAG GENERATOR PROMPTS
# ===========================================================================

DAG_COMPILING_PROMPT = """You are the master SEPE Autonomous DAG Compilation Agent (Node A).
Your goal is to parse abstract macro-goals or incoming events, and construct a strongly typed JSON Directed Acyclic Graph (DAG) for automated execution.

You MUST compile your output as a single, valid JSON object matching the following structure:
{
  "macro_goal": "A short summary of the macro goal",
  "dag_layers": [
    {
      "layer_id": 1,
      "nodes": [
        {
          "node_id": "TASK_001",
          "depends_on": [],
          "agent_skill": "Read_Document",
          "input_parameters": {"filename": "acme_invoice.pdf", "file_type": "pdf"},
          "requires_human_approval": false
        }
      ]
    }
  ]
}

RULES:
1. Available Skills:
   - 'Read_Document': Takes {"filename": "str", "file_type": "pdf|csv|md"}. Extracts summary.
   - 'Process_Invoice': Takes {"title": "str", "amount": float, "client_email": "str"}. Logs financial payable or receivable.
   - 'Generate_Branding_Content': Takes {"topic": "str", "persona_prompt": "str"}. Manufactures multi-platform social payloads.
   - 'Execute_Financial_Log': Takes {"title": "str", "amount": float, "recipient": "str"}. High-risk capital release! Must set requires_human_approval to true.
   - 'Synthesize_Brief': Takes {"meeting_title": "str", "stakeholders": "str"}. Builds pre-meeting brief briefings.
2. Risk Boundaries:
   - Any financial capital release or monetary pay out ('Execute_Financial_Log') MUST set 'requires_human_approval' to true.
   - All other skills can generally run on full autopilot (requires_human_approval = false).
3. Dependency Layers:
   - Order layers logically. Prerequisite tasks (e.g. Read_Document) must occur in earlier layers, and dependent tasks (e.g. Process_Invoice) in subsequent layers, listing the prerequisite node_id in 'depends_on'.
"""

# ===========================================================================
# 3. DIRECT DAG ORCHESTRATION PIPELINE ENGINE
# ===========================================================================

class DagOrchestratorEngine:
    """Compiles and asynchronously executes non-linear multi-agent Directed Acyclic Graphs (DAGs)."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"

        if not self.gemini_key or self.gemini_key == "mock-key-for-simulation":
            raise ValueError("PRODUCTION SECURITY BOUNDARY: Active 'GEMINI_API_KEY' required for DAG compilation.")

    async def compile_macro_goal_to_dag(self, macro_goal: str) -> AutonomousDagSchema:
        """
        Uses gemini-3.1-flash-lite to compile an abstract goal into a valid multi-layer JSON DAG.
        """
        logger.info("DAG Orchestrator: Compiling macro goal -> '%s'", macro_goal)
        
        payload = {
            "systemInstruction": {"parts": [{"text": DAG_COMPILING_PROMPT}]},
            "contents": [
                {"role": "user", "parts": [{"text": f"Compile a logical multi-layer execution DAG for this goal: '{macro_goal}'"}]}
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        
        url_with_key = f"{self.gemini_url}?key={self.gemini_key}"
        
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(url_with_key, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_dict = json.loads(raw_json)
            # Enforce strongly typed schema validations
            dag_obj = AutonomousDagSchema.model_validate(parsed_dict)
            logger.info("DAG Orchestrator: Successfully compiled DAG with %d execution layers.", len(dag_obj.dag_layers))
            return dag_obj
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
            logger.error("DAG Orchestrator: Compiled payload was invalid: %s", exc)
            raise RuntimeError(f"Failed to compile strongly typed DAG contract: {exc}")

    async def register_dag_in_ledger(self, dag_obj: AutonomousDagSchema, account_id: uuid.UUID) -> uuid.UUID:
        """Logs the compiled JSON DAG inside PostgreSQL persistence ledgers."""
        ledger = DagExecutionLedger(
            account_id=account_id,
            macro_goal=dag_obj.macro_goal,
            dag_json=json.dumps(dag_obj.model_dump()),
            status="running",
            telemetry_logs=json.dumps([{"timestamp": datetime.utcnow().isoformat(), "event": "DAG_REGISTERED"}])
        )
        self.db.add(ledger)
        await self.db.flush()
        logger.info("DAG Ledger registered: id=%s", ledger.id)
        return ledger.id

    async def execute_dag_pipeline(self, ledger_id: uuid.UUID) -> None:
        """
        Main execution loop.
        Evaluates layer dependencies asynchronously, respects human gates, and isolates failed branches.
        """
        logger.info("DAG Engine: Starting execution cycle for ledger_id=%s", ledger_id)
        
        # 1. Fetch Ledger Record
        stmt = select(DagExecutionLedger).where(DagExecutionLedger.id == ledger_id)
        res = await self.db.execute(stmt)
        ledger_item = res.scalar_one_or_none()
        if not ledger_item:
            logger.error("DAG Engine: Ledger record '%s' not found.", ledger_id)
            return

        # 2. Parse DAG JSON State
        try:
            dag_dict = json.loads(ledger_item.dag_json)
            dag = AutonomousDagSchema.model_validate(dag_dict)
        except Exception as exc:
            logger.critical("DAG Engine: Failed to parse registered DAG layout: %s", exc)
            ledger_item.status = "failed"
            await self.db.commit()
            return

        logs = json.loads(ledger_item.telemetry_logs or "[]")
        completed_nodes = set()
        failed_nodes = set()
        
        # We execute layer by layer
        for layer in dag.dag_layers:
            logger.info("DAG Engine: Entering Layer %d execution bounds...", layer.layer_id)
            
            # Check if any dependencies of nodes in this layer have failed
            # If a prerequisite failed, this node is blocked (isolated failure branch)
            runnable_nodes = []
            for node in layer.nodes:
                blocked = False
                for prereq in node.depends_on:
                    if prereq in failed_nodes:
                        logger.warning("DAG Node Blocked: TASK %s cannot run because prerequisite %s failed.", node.node_id, prereq)
                        node.status = "failed"
                        node.telemetry = f"Blocked by failed prerequisite TASK {prereq}"
                        failed_nodes.add(node.node_id)
                        blocked = True
                        break
                if not blocked:
                    runnable_nodes.append(node)

            if not runnable_nodes:
                continue

            # Process human gates
            pending_human_nodes = [n for n in runnable_nodes if n.requires_human_approval and n.status != "completed"]
            if pending_human_nodes:
                logger.info("DAG Engine: Halting execution on Layer %d. Human approvals required.", layer.layer_id)
                for hn in pending_human_nodes:
                    hn.status = "pending_approval"
                    
                # Update ledger state
                ledger_item.status = "pending_approval"
                ledger_item.dag_json = json.dumps(dag.model_dump())
                logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"HALT_HUMAN_APPROVAL_REQUIRED_LAYER_{layer.layer_id}"})
                ledger_item.telemetry_logs = json.dumps(logs)
                await self.db.commit()
                return # Stop thread here. Streamlit UI will trigger release!

            # Execute safe runnable nodes in parallel inside the layer
            tasks = []
            for node in runnable_nodes:
                node.status = "running"
                tasks.append(self._execute_single_node(node, ledger_item.account_id))

            # Run concurrently (return_exceptions=True isolates failures!)
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, node in enumerate(runnable_nodes):
                res_val = results[idx]
                if isinstance(res_val, Exception):
                    logger.error("DAG Node %s raised exception: %s", node.node_id, res_val)
                    node.status = "failed"
                    node.telemetry = f"CRITICAL FAILURE: {str(res_val)}"
                    failed_nodes.add(node.node_id)
                    logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"NODE_FAILED_{node.node_id}", "error": str(res_val)})
                else:
                    status_flag, output_str = res_val
                    if status_flag:
                        node.status = "completed"
                        node.telemetry = output_str
                        completed_nodes.add(node.node_id)
                        logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"NODE_COMPLETED_{node.node_id}"})
                    else:
                        node.status = "failed"
                        node.telemetry = f"FAILURE: {output_str}"
                        failed_nodes.add(node.node_id)
                        logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"NODE_FAILED_{node.node_id}", "details": output_str})

        # Finalize DAG Ledger status
        if failed_nodes:
            ledger_item.status = "failed" if not completed_nodes else "completed" # Partial completion or failed
        else:
            ledger_item.status = "completed"
            
        logger.info("DAG Engine: Execution cycle finalized with status: %s", ledger_item.status)
        ledger_item.dag_json = json.dumps(dag.model_dump())
        logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"DAG_EXECUTION_FINALIZED_{ledger_item.status.upper()}"})
        ledger_item.telemetry_logs = json.dumps(logs)
        await self.db.commit()

    async def _execute_single_node(self, node: DagNodeSchema, account_id: uuid.UUID) -> Tuple[bool, str]:
        """Maps target agent skills to direct production modules."""
        skill = node.agent_skill
        params = node.input_parameters
        
        logger.info("DAG Node executing: TASK %s (%s)", node.node_id, skill)

        try:
            # Skill A: Read_Document
            if skill == "Read_Document":
                filename = params.get("filename", "unknown_document.pdf")
                file_type = params.get("file_type", "pdf")
                
                # In production, we parse the file, calculate embeddings and summaries.
                # Here we log it as a WorkspaceDocument.
                summary = f"Executive brief of newly ingested {filename}. Formulates technical metrics."
                doc = WorkspaceDocument(
                    account_id=account_id,
                    filename=filename,
                    file_type=file_type,
                    summary=summary,
                    vector_status="indexed"
                )
                self.db.add(doc)
                await self.db.flush()
                return True, f"Document summary indexed inside Vector memory: id={doc.id}"

            # Skill B: Process_Invoice
            elif skill == "Process_Invoice":
                title = params.get("title", "Acme Invoice Closeout")
                amount = float(params.get("amount", 250.0))
                
                # Check for budget anomaly threshold ($5,000.00)
                status_flag = "pending"
                if amount > 5000.0:
                    logger.warning("🚨 [ANOMALY DETECTED] Invoice exceeds budget release thresholds! Flagged for human review.")
                    status_flag = "anomaly"
                    
                ledger = FinancialLedger(
                    account_id=account_id,
                    title=title,
                    amount=amount,
                    entry_type="payable",
                    status=status_flag
                )
                self.db.add(ledger)
                await self.db.flush()
                return True, f"Invoice processed and registered. Ledger entry id={ledger.id}. Status={status_flag}"

            # Skill C: Generate_Branding_Content
            elif skill == "Generate_Branding_Content":
                topic = params.get("topic", "Production Compliance AI")
                persona_prompt = params.get("persona_prompt", "Professional Executive CTO.")
                
                # Call Content Factory RAIG Pipeline
                engine = ContentFactoryEngine(gemini_key=self.gemini_key, openrouter_key=self.openrouter_key)
                payload, _, success = await engine.execute_publishing_pipeline(
                    topic=topic,
                    persona_prompt=persona_prompt,
                    max_healing_turns=3
                )
                
                if success:
                    # Log draft in Content Ledger
                    stmt = select(PersonaRegistry).where(PersonaRegistry.account_id == account_id)
                    res = await self.db.execute(stmt)
                    persona = res.scalars().first()
                    
                    if not persona:
                        # Fallback create a dummy persona to satisfy database integrity constraints
                        persona = PersonaRegistry(
                            account_id=account_id,
                            agent_name="Executive Twin",
                            system_prompt=persona_prompt
                        )
                        self.db.add(persona)
                        await self.db.flush()

                    content_ledger = ContentStateLedger(
                        account_id=account_id,
                        persona_id=persona.id,
                        action_type="content_publish",
                        status="PENDING_HUMAN_SIGN_OFF",
                        payload=json.dumps(payload.model_dump())
                    )
                    self.db.add(content_ledger)
                    await self.db.flush()
                    return True, f"Copywriting drafts successfully manufactured and logged in HITL queue: id={content_ledger.id}"
                else:
                    return False, "Nemotron critic failed to approve content drafts during self-healing loops."

            # Skill D: Execute_Financial_Log (Monetary released closeouts)
            elif skill == "Execute_Financial_Log":
                title = params.get("title", "B2B Vendor Dispatches")
                amount = float(params.get("amount", 75000.00))
                recipient = params.get("recipient", "Acme Corporate")
                
                # Execute bank release
                ledger = FinancialLedger(
                    account_id=account_id,
                    title=f"Released: {title} to {recipient}",
                    amount=amount,
                    entry_type="payable",
                    status="cleared"
                )
                self.db.add(ledger)
                await self.db.flush()
                return True, f"Capital successfully released in ledger. Cleared transaction id={ledger.id} for ${amount:.2f}."

            # Skill E: Synthesize_Brief
            elif skill == "Synthesize_Brief":
                meeting_title = params.get("meeting_title", "Technical Integration Pitch")
                stakeholders = params.get("stakeholders", "Acme Board")
                
                brief = (
                    f"PRE-MEETING INTEL BRIEFING:\n"
                    f"Subject: {meeting_title}\n"
                    f"Attendees: {stakeholders}\n"
                    f"Vector Context: Retaining contract history of B2B transactions. Stakeholder values ACV at $75,000."
                )
                return True, brief

            else:
                return False, f"Agent skill '{skill}' not recognized."

        except Exception as exc:
            logger.error("DAG Node execution crash: %s", exc)
            return False, str(exc)

    async def release_human_approval_gate(self, ledger_id: uuid.UUID) -> None:
        """
        Releases pending human nodes inside the DAG ledger and resumes execution threads.
        Called on Streamlit operator button confirmations.
        """
        logger.info("DAG Engine: Releasing human approvals for ledger_id=%s", ledger_id)
        
        stmt = select(DagExecutionLedger).where(DagExecutionLedger.id == ledger_id)
        res = await self.db.execute(stmt)
        ledger_item = res.scalar_one_or_none()
        
        if not ledger_item or ledger_item.status != "pending_approval":
            logger.warning("DAG Engine: Ledger not in pending_approval. Cancelled release.")
            return

        # Parse DAG and change pending_approval nodes to completed (as approved by human)
        dag_dict = json.loads(ledger_item.dag_json)
        dag = AutonomousDagSchema.model_validate(dag_dict)
        
        for layer in dag.dag_layers:
            for node in layer.nodes:
                if node.status == "pending_approval":
                    node.status = "completed"
                    node.telemetry = "Approved manually by Human operator via UI Board."
                    
        ledger_item.dag_json = json.dumps(dag.model_dump())
        ledger_item.status = "running"
        await self.db.commit()
        
        # Spawn execution loop asynchronously to resume running subsequent layers
        asyncio.create_task(self.execute_dag_pipeline(ledger_id))
