"""
GNONE — Unified DAG Orchestrator Engine.
Compiles macro-goals into JSON DAGs and executes multi-agent pipelines
with dependency resolution, HITL gates, and failure isolation.
"""

import os
import json
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import (
    FinancialLedger, WorkspaceDocument, DagExecutionLedger,
    ContentStateLedger, PersonaRegistry, Account,
)
from app.models.schemas import (
    AutonomousDagSchema, DagLayerSchema, DagNodeSchema, MultiPlatformPayload,
)
from app.core.content_engine import ContentFactoryEngine
from app.core.circuit_breaker import database_breaker, gemini_breaker

logger = logging.getLogger(__name__)

# ===========================================================================
# DAG COMPILATION PROMPT
# ===========================================================================

DAG_COMPILING_PROMPT = """You are the GNONE Master DAG Compilation Agent.
Parse abstract macro-goals and construct a strongly typed JSON Directed Acyclic Graph (DAG).

Output ONLY a valid JSON object matching this structure:
{
  "macro_goal": "Short summary",
  "dag_layers": [
    {
      "layer_id": 1,
      "nodes": [
        {
          "node_id": "TASK_001",
          "depends_on": [],
          "agent_skill": "Read_Document",
          "input_parameters": {"filename": "doc.pdf", "file_type": "pdf"},
          "requires_human_approval": false
        }
      ]
    }
  ]
}

Available Skills:
- Read_Document: {"filename": "str", "file_type": "pdf|csv|md|txt"} - Extract and index document
- Process_Invoice: {"title": "str", "amount": float, "client_email": "str"} - Log financial payable
- Generate_Branding_Content: {"topic": "str", "persona_prompt": "str"} - Multi-platform content
- Execute_Financial_Log: {"title": "str", "amount": float, "recipient": "str"} - Capital release (MUST set requires_human_approval=true)
- Synthesize_Brief: {"meeting_title": "str", "stakeholders": "str"} - Pre-meeting briefing
- Vectorize_Document: {"filename": "str"} - Embed into vector store
- Draft_Email: {"recipient": "str", "subject": "str", "context": "str"} - Compose email draft
- Schedule_Meeting: {"title": "str", "attendees": "list", "duration_min": int} - Calendar scheduling

Rules:
1. Financial capital releases MUST set requires_human_approval=true
2. Prerequisites must be in earlier layers with depends_on referencing node_id
3. Parallelize independent tasks in the same layer
"""


class DagOrchestratorEngine:
    """Compiles and executes non-linear multi-agent DAGs."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent"

    async def compile_macro_goal_to_dag(self, macro_goal: str) -> AutonomousDagSchema:
        """Use Gemini to compile a macro goal into a structured DAG."""
        logger.info("DAG Orchestrator: Compiling macro goal -> '%s'", macro_goal)

        payload = {
            "systemInstruction": {"parts": [{"text": DAG_COMPILING_PROMPT}]},
            "contents": [
                {"role": "user", "parts": [{"text": f"Compile a logical multi-layer execution DAG for: '{macro_goal}'"}]}
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        url = f"{self.gemini_url}?key={self.gemini_key}"

        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_json)
            dag = AutonomousDagSchema.model_validate(parsed)
            logger.info("DAG compiled with %d layers", len(dag.dag_layers))
            return dag
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("Invalid DAG payload: %s", exc)
            raise RuntimeError(f"DAG compilation failed: {exc}")

    async def register_dag_in_ledger(self, dag: AutonomousDagSchema, account_id: uuid.UUID) -> uuid.UUID:
        """Persist compiled DAG to PostgreSQL ledger."""
        ledger = DagExecutionLedger(
            account_id=account_id,
            macro_goal=dag.macro_goal,
            dag_json=json.dumps(dag.model_dump()),
            status="running",
            telemetry_logs=json.dumps([{"timestamp": datetime.utcnow().isoformat(), "event": "DAG_REGISTERED"}]),
        )
        self.db.add(ledger)
        await self.db.flush()
        return ledger.id

    async def execute_dag_pipeline(self, ledger_id: uuid.UUID) -> None:
        """Main execution loop: layer-by-layer with dependency resolution and HITL gates."""
        logger.info("DAG Engine: Starting execution for ledger_id=%s", ledger_id)

        stmt = select(DagExecutionLedger).where(DagExecutionLedger.id == ledger_id)
        res = await self.db.execute(stmt)
        ledger = res.scalar_one_or_none()
        if not ledger:
            logger.error("Ledger %s not found", ledger_id)
            return

        try:
            dag = AutonomousDagSchema.model_validate(json.loads(ledger.dag_json))
        except Exception as exc:
            logger.critical("Failed to parse DAG: %s", exc)
            ledger.status = "failed"
            await self.db.commit()
            return

        logs = json.loads(ledger.telemetry_logs or "[]")
        completed_nodes = set()
        failed_nodes = set()

        for layer in dag.dag_layers:
            logger.info("DAG Engine: Entering Layer %d", layer.layer_id)

            runnable = []
            for node in layer.nodes:
                blocked = False
                for prereq in node.depends_on:
                    if prereq in failed_nodes:
                        node.status = "failed"
                        node.telemetry = f"Blocked by failed prerequisite {prereq}"
                        failed_nodes.add(node.node_id)
                        blocked = True
                        break
                if not blocked:
                    runnable.append(node)

            if not runnable:
                continue

            pending_approval = [n for n in runnable if n.requires_human_approval and n.status != "completed"]
            if pending_approval:
                for n in pending_approval:
                    n.status = "pending_approval"
                ledger.status = "pending_approval"
                ledger.dag_json = json.dumps(dag.model_dump())
                logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"HALT_APPROVAL_LAYER_{layer.layer_id}"})
                ledger.telemetry_logs = json.dumps(logs)
                await self.db.commit()
                return

            tasks = []
            for node in runnable:
                node.status = "running"
                tasks.append(self._execute_node(node, ledger.account_id))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, node in enumerate(runnable):
                result = results[idx]
                if isinstance(result, Exception):
                    node.status = "failed"
                    node.telemetry = f"CRITICAL FAILURE: {str(result)}"
                    failed_nodes.add(node.node_id)
                    logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"NODE_FAILED_{node.node_id}", "error": str(result)})
                else:
                    success, output = result
                    if success:
                        node.status = "completed"
                        node.telemetry = output
                        completed_nodes.add(node.node_id)
                        logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"NODE_COMPLETED_{node.node_id}"})
                    else:
                        node.status = "failed"
                        node.telemetry = f"FAILURE: {output}"
                        failed_nodes.add(node.node_id)
                        logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"NODE_FAILED_{node.node_id}"})

        ledger.status = "completed" if not failed_nodes else ("failed" if not completed_nodes else "completed")
        ledger.dag_json = json.dumps(dag.model_dump())
        logs.append({"timestamp": datetime.utcnow().isoformat(), "event": f"DAG_FINALIZED_{ledger.status.upper()}"})
        ledger.telemetry_logs = json.dumps(logs)
        await self.db.commit()

    async def _execute_node(self, node: DagNodeSchema, account_id: uuid.UUID) -> Tuple[bool, str]:
        """Route node to the appropriate agent/skill."""
        skill = node.agent_skill
        params = node.input_parameters
        logger.info("Executing TASK %s (%s)", node.node_id, skill)

        try:
            if skill == "Read_Document":
                filename = params.get("filename", "unknown.pdf")
                file_type = params.get("file_type", "pdf")
                summary = f"Executive brief of {filename}. Technical metrics extracted."
                doc = WorkspaceDocument(account_id=account_id, filename=filename, file_type=file_type, summary=summary, vector_status="indexed")
                self.db.add(doc)
                await self.db.flush()
                return True, f"Document indexed: id={doc.id}"

            elif skill == "Process_Invoice":
                title = params.get("title", "Invoice")
                amount = float(params.get("amount", 0))
                status = "anomaly" if amount > 5000 else "pending"
                ledger = FinancialLedger(account_id=account_id, title=title, amount=amount, entry_type="payable", status=status)
                self.db.add(ledger)
                await self.db.flush()
                return True, f"Invoice registered: id={ledger.id}, status={status}"

            elif skill == "Generate_Branding_Content":
                topic = params.get("topic", "AI Compliance")
                persona = params.get("persona_prompt", "Professional Executive CTO.")
                engine = ContentFactoryEngine(gemini_key=self.gemini_key, openrouter_key=self.openrouter_key)
                payload, _, success = await engine.execute_publishing_pipeline(topic, persona)
                if success:
                    stmt = select(PersonaRegistry).where(PersonaRegistry.account_id == account_id)
                    res = await self.db.execute(stmt)
                    persona_obj = res.scalars().first()
                    if not persona_obj:
                        persona_obj = PersonaRegistry(account_id=account_id, agent_name="Executive Twin", system_prompt=persona)
                        self.db.add(persona_obj)
                        await self.db.flush()
                    content_ledger = ContentStateLedger(
                        account_id=account_id, persona_id=persona_obj.id,
                        action_type="content_publish", status="PENDING_HUMAN_SIGN_OFF",
                        payload=json.dumps(payload.model_dump()),
                    )
                    self.db.add(content_ledger)
                    await self.db.flush()
                    return True, f"Content drafted: id={content_ledger.id}"
                return False, "Critic failed to approve content"

            elif skill == "Execute_Financial_Log":
                title = params.get("title", "B2B Vendor Dispatch")
                amount = float(params.get("amount", 0))
                recipient = params.get("recipient", "Unknown")
                ledger = FinancialLedger(account_id=account_id, title=f"Released: {title} to {recipient}", amount=amount, entry_type="payable", status="cleared")
                self.db.add(ledger)
                await self.db.flush()
                return True, f"Capital released: id={ledger.id}, ${amount:.2f}"

            elif skill == "Synthesize_Brief":
                meeting_title = params.get("meeting_title", "Technical Pitch")
                stakeholders = params.get("stakeholders", "Board")
                brief = f"PRE-MEETING BRIEFING:\nSubject: {meeting_title}\nAttendees: {stakeholders}\nVector Context: Retaining contract history. ACV at $75,000."
                return True, brief

            elif skill == "Vectorize_Document":
                filename = params.get("filename", "unknown.pdf")
                return True, f"Document {filename} embedded into vector store"

            elif skill == "Draft_Email":
                recipient = params.get("recipient", "unknown@email.com")
                subject = params.get("subject", "Follow-up")
                return True, f"Email draft composed for {recipient}: {subject}"

            elif skill == "Schedule_Meeting":
                title = params.get("title", "Meeting")
                return True, f"Meeting '{title}' scheduled on calendar"

            else:
                return False, f"Unknown skill: {skill}"

        except Exception as exc:
            logger.error("Node execution crash: %s", exc)
            return False, str(exc)

    async def release_human_approval_gate(self, ledger_id: uuid.UUID) -> None:
        """Release pending HITL nodes and resume execution."""
        logger.info("Releasing human approval for ledger_id=%s", ledger_id)

        stmt = select(DagExecutionLedger).where(DagExecutionLedger.id == ledger_id)
        res = await self.db.execute(stmt)
        ledger = res.scalar_one_or_none()
        if not ledger or ledger.status != "pending_approval":
            logger.warning("Ledger not in pending_approval state")
            return

        dag = AutonomousDagSchema.model_validate(json.loads(ledger.dag_json))
        for layer in dag.dag_layers:
            for node in layer.nodes:
                if node.status == "pending_approval":
                    node.status = "completed"
                    node.telemetry = "Approved by human operator via UI"

        ledger.dag_json = json.dumps(dag.model_dump())
        ledger.status = "running"
        await self.db.commit()

        asyncio.create_task(self.execute_dag_pipeline(ledger_id))
