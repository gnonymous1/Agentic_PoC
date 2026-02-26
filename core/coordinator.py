import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.llm_router import LLMRouter
from core.memory import VectorMemory
from core.self_improver import SelfImprover
from core.monitoring import ObservabilityEngine
from core.learning import AdaptiveLearningEngine
from core.reasoning_engine import AdvancedReasoningEngine
from core.human_loop import HumanInteractionManager
from core.device_manager import DeviceManager
from billing.tiers import UsageQuotaManager, ServiceTier
from core.meta_learning import MetaLearningEngine
from agents.base_agent import BaseAgent

class AgentMessage:
    """Message passed between agents."""
    def __init__(
        self,
        sender: str,
        receiver: str,
        content: dict,
        msg_type: str = "task",  # task, result, query, alert
        priority: int = 5,
    ):
        self.id = str(uuid.uuid4())
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.msg_type = msg_type
        self.priority = priority
        self.timestamp = datetime.now()


class CoordinatorAgent:
    """
    Meta-agent that:
    1. Understands complex requests
    2. Decomposes into sub-tasks
    3. Assigns to specialist agents
    4. Coordinates parallel execution
    5. Synthesizes results
    6. Self-improves from outcomes
    """

    def __init__(self, config: dict):
        self.config = config
        self.observability = ObservabilityEngine(config)
        self.llm = LLMRouter(config, observability=self.observability)
        self.memory = VectorMemory(config)
        self.learning = AdaptiveLearningEngine(config, self.memory)
        self.reasoning_engine = AdvancedReasoningEngine(self.llm)
        self.human_loop = HumanInteractionManager()
        self.device_manager = DeviceManager()
        self.quota_manager = UsageQuotaManager()
        self.meta_learner = MetaLearningEngine(self.llm, self.memory)
        self.self_improver = SelfImprover(config, self.llm, self.memory)
        self.audit_trail = []
        self.agents: Dict[str, BaseAgent] = {}
        self.message_bus: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, dict] = {}
        self.agent_capabilities: Dict[str, List[str]] = {}
        self.reasoning_history: List[dict] = []

    def register_agent(self, agent: BaseAgent):
        """Register a specialist agent and catalog its capabilities."""
        self.agents[agent.name] = agent
        self.agent_capabilities[agent.name] = agent.get_capabilities()
        agent.set_message_bus(self.message_bus)
        agent.set_llm_router(self.llm)

    async def process(self, user_input: str, source: str = None, task_id: str = None, user_id: str = "default_user", context: dict = None) -> str:
        """Process a request from start to finish."""
        task_id = task_id or str(uuid.uuid4())
        
        # 0. QUOTA CHECK
        if not self.quota_manager.check_quota(user_id, "parallel_tasks"):
            return "Error: Parallel task quota exceeded for your tier."
        
        self.quota_manager.record_usage(user_id, "task_start")
        
        # Start Root Trace
        root_span = self.observability.start_trace(
            operation="process_request",
            agent="coordinator",
            metadata={"user_input": user_input, "source": source, "task_id": task_id}
        )

        # Update device activity if source is a device
        if source:
            self.device_manager.update_activity(source)

        try:
            # 1. DEEP REASONING
            reason_span = self.observability.start_trace("reasoning", "coordinator", root_span.trace_id)
            reasoning = await self._reason(user_input, context)
            self.observability.end_trace(reason_span)

            # 2. TASK DECOMPOSITION
            decomp_span = self.observability.start_trace("decomposition", "coordinator", root_span.trace_id)
            task_plan = await self._decompose(user_input, reasoning)
            self.observability.end_trace(decomp_span)

            # 3. EXECUTION
            exec_span = self.observability.start_trace("execution", "coordinator", root_span.trace_id)
            results = await self._execute_plan(task_id, task_plan, parent_trace_id=root_span.trace_id)
            self.observability.end_trace(exec_span)

            # 4. SYNTHESIS
            synth_span = self.observability.start_trace("synthesis", "coordinator", root_span.trace_id)
            final_response = await self._synthesize(user_input, task_plan, results)
            self.observability.end_trace(synth_span)

            # 5. SELF-IMPROVEMENT & LEARNING
            improve_span = self.observability.start_trace("self_improvement", "coordinator", root_span.trace_id)
            await self.learning.learn_from_interaction(user_input, str(final_response), task_type="general")
            await self.self_improver.learn_from_execution(
                user_input, task_plan, results, final_response
            )
            self.observability.end_trace(improve_span)

            # Store in memory
            await self.memory.store({
                "type": "execution",
                "task_id": task_id,
                "user_input": user_input,
                "plan": task_plan,
                "results": results,
                "response": final_response,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            self.observability.end_trace(root_span, status="error", error=str(e))
            raise e
        finally:
            self.quota_manager.record_usage(user_id, "task_end")
            self.observability.end_trace(root_span, status="success" if "final_response" in locals() else "error")
            
            # Phase 12 Evolution Trigger (Occasional check)
            if datetime.now().second % 60 == 0: # Mock periodic check
                asyncio.create_task(self.evolve())
                
            return final_response if "final_response" in locals() else "Process failed"

    async def evolve(self):
        """The AI self-improvement loop for Phase 12."""
        print("[EVO] Starting self-evolution cycle...")
        insight = await self.meta_learner.distill_knowledge()
        if insight:
            print(f"[EVO] Discovered new efficiency: {insight['discovered_workflow']}")
            await self.self_improver.autonomous_tool_generation({
                "capability_name": insight["discovered_workflow"]
            })

    async def _reason(self, user_input: str, context: dict = None) -> dict:
        """Deep reasoning about the request."""
        base_prompt = f"""You are the COORDINATOR. Analyze this request: "{user_input}"
        Available Agents: {json.dumps(self.agent_capabilities)}
        
        Output JSON:
        {{
            "intent": "intent description",
            "complexity": "simple|complex",
            "approach": "strategy",
            "confidence": 0.0-1.0
        }}
        """
        
        prompt = await self.learning.get_refined_prompt(base_prompt, "reasoning")
        
        response = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type="reasoning"
        )
        
        try:
            analysis = json.loads(response["content"])
        except json.JSONDecodeError:
            analysis = {"intent": user_input, "complexity": "simple", "approach": "direct", "confidence": 0.0}
        
        # 1. Check for clarification (Confidence Gate)
        if analysis.get("confidence", 1.0) < 0.5:
            print(f"[GATE] Low confidence ({analysis['confidence']}). Requesting clarification...")
            int_id = await self.human_loop.request_clarification(
                f"I'm not sure I understand. Did you mean: {analysis['intent']}?"
            )
            clarification = await self.human_loop.wait_for_response(int_id)
            # Re-run reasoning with clarification
            return await self._reason(f"{user_input} (Clarification: {clarification})", context)

        # 2. If complexity is high, perform advanced reasoning
        if analysis.get("complexity") == "complex":
            # Use advanced reasoning engine for complex tasks
            advanced_thought = await self.reasoning_engine.reason_with_reflection(user_input, iterations=1)
            analysis["advanced_reasoning"] = advanced_thought

        return analysis

    async def _decompose(self, user_input: str, reasoning: dict) -> dict:
        """Decompose into sub-tasks."""
        base_prompt = f"""Create an execution plan for: "{user_input}"
        Reasoning: {json.dumps(reasoning)}
        Available Agents: {json.dumps(self.agent_capabilities)}
        
        Output JSON:
        {{
            "execution_groups": [
                {{
                    "group_id": 1,
                    "parallel": false,
                    "tasks": [
                        {{
                            "task_id": "t1",
                            "agent": "agent_name",
                            "action": "action_name",
                            "params": {{}}
                        }}
                    ]
                }}
            ]
        }}
        """
        
        prompt = await self.learning.get_refined_prompt(base_prompt, "decomposition")
        
        response = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type="reasoning"
        )
        
        try:
            return json.loads(response["content"])
        except:
            return {"execution_groups": []}

    async def _execute_plan(self, task_id: str, plan: dict, parent_trace_id: str = None) -> dict:
        """Execute the decomposed plan."""
        self.active_tasks[task_id] = {"plan": plan, "status": "running", "results": {}}
        all_results = {}

        for group in plan.get("execution_groups", []):
            group_id = group["group_id"]
            group_results = {}
            tasks_coroutines = []
            task_ids = []

            # Prepare tasks for parallel execution
            for task in group.get("tasks", []):
                # 3a. SENSITIVE TASK CHECK (Approval Gate)
                if self._is_sensitive(task):
                    print(f"[GATE] Sensitive task detected: {task['action']}. Awaiting approval...")
                    int_id = await self.human_loop.request_approval(task['action'], task)
                    approved = await self.human_loop.wait_for_response(int_id)
                    if not approved:
                        group_results[task["task_id"]] = {"status": "rejected", "message": "User denied approval"}
                        continue

                agent_name = task.get("agent")
                action = task["action"]
                params = task.get("params", {})
                
                tasks_coroutines.append(self._execute_single_task(
                    agent_name, action, params, task["task_id"], parent_trace_id
                ))
                task_ids.append(task["task_id"])

            # Execute all tasks in this group in parallel
            results_list = await asyncio.gather(*tasks_coroutines, return_exceptions=True)

            # Process results
            for i, res in enumerate(results_list):
                t_id = task_ids[i]
                if isinstance(res, Exception):
                     group_results[t_id] = {"status": "error", "error": str(res)}
                else:
                     group_results[t_id] = res

            all_results[group_id] = group_results
            self._audit_log(f"Execution Group {group['group_id']} completed with status: {group_results}")
            
        return all_results

    def _audit_log(self, message: str):
        """Append to system audit trail."""
        timestamp = datetime.now().isoformat()
        self.audit_trail.append(f"[{timestamp}] {message}")
        # Could also write to file or database here

    async def _execute_single_task(self, agent_name: str, action: str, params: dict, task_id: str, parent_trace_id: str) -> dict:
        """Execute a single task with tracing."""
        # Trace individual task
        task_span = self.observability.start_trace(
            operation=f"{agent_name}.{action}",
            agent=agent_name,
            parent_trace_id=parent_trace_id,
            metadata={"task_id": task_id, "params": params}
        )

        agent = self.agents.get(agent_name)
        if agent:
            try:
                res = await agent.execute(action, params)
                self.observability.end_trace(task_span, status="success")
                return {"status": "success", "data": res}
            except Exception as e:
                self.observability.end_trace(task_span, status="error", error=str(e))
                return {"status": "error", "error": str(e)}
        else:
            self.observability.end_trace(task_span, status="error", error="Agent not found")
            return {"status": "error", "error": "Agent not found"}

    def _is_sensitive(self, task: dict) -> bool:
        """Heuristic check for sensitive operations requiring human approval."""
        action = task.get("action", "").lower()
        sensitive_keywords = ["delete", "remove", "wipe", "format", "terminate", "reboot"]
        return any(k in action for k in sensitive_keywords)

    async def _synthesize(self, user_input: str, plan: dict, results: dict) -> str:
        """Synthesize results."""
        prompt = f"""Summarize these results for the user:
        Request: {user_input}
        Results: {json.dumps(results)}
        
        Output JSON: {{ "summary": "message", "details": [] }}
        """
        
        response = await self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            task_type="general"
        )
        try:
            return json.loads(response["content"])
        except:
            return {"summary": "Execution complete.", "details": results}

    async def autonomous_think(self) -> Optional[dict]:
        """Proactive thinking cycle."""
        # Simplified for PoC
        return None
