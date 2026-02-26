import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from core.llm_router import LLMRouter
from core.memory import VectorMemory

class SelfImprover:
    """
    Self-improvement engine that:
    1. Learns from execution outcomes
    2. Suggests improvements
    3. Analyzes failures
    """

    def __init__(self, config: dict, llm: LLMRouter, memory: VectorMemory):
        self.config = config
        self.llm = llm
        self.memory = memory
        self.improvement_log: List[dict] = []

    async def learn_from_execution(
        self,
        user_input: str,
        plan: dict,
        results: dict,
        response: dict,
    ):
        """Analyze an execution outcome and extract learnings."""
        
        # Calculate success rate (simplified)
        total_tasks = 0
        success_count = 0
        failures = []
        
        for group_id, group_results in results.items():
            for task_id, task_result in group_results.items():
                total_tasks += 1
                if task_result.get("status") == "success":
                    success_count += 1
                else:
                    failures.append(task_result)

        success_rate = success_count / max(total_tasks, 1)

        # Store learning if there was a failure
        if failures:
            learning = {
                "input": user_input,
                "failures": failures,
                "success_rate": success_rate,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.memory.store({
                "type": "learning",
                "category": "failure_analysis",
                "data": learning
            })
            self.improvement_log.append(learning)

    async def self_improve_prompts(self):
        """Analyze recent failures and suggest prompt improvements."""
        # Simplified PoC implementation
        recent_failures = [
            log for log in self.improvement_log[-10:] 
            if log["success_rate"] < 1.0
        ]
        
        if not recent_failures:
            return None
            
        prompt = f"""Analyze these recent failures: {json.dumps(recent_failures, default=str)}
        Suggest 1 prompt improvement for the Coordinator.
        Output JSON: {{ "improvement": "description", "suggested_change": "text" }}
        """
        
        try:
            response = await self.llm.complete(
                messages=[{"role": "user", "content": prompt}],
                task_type="reasoning"
            )
            return json.loads(response["content"])
        except:
            return None

    async def autonomous_tool_generation(self, capability_data: dict):
        """
        Actually writes a new Python tool to the dynamic_tools folder.
        This is the core of Phase 12 - the system expanding itself.
        """
        name = capability_data["capability_name"].lower().replace(" ", "_")
        target_path = f"c:/Users/cw_21/Desktop/Agentic_PoC/agent_fabric/dynamic_tools/auto_{name}.py"
        
        prompt = f"""Write a Python script for a new OMNIOS tool.
        Capability: {capability_data["capability_name"]}
        Description: Automatically discovered as useful.
        
        Requirements:
        1. Function name: {name}
        2. Must have docstring.
        3. Module must export 'name' and 'description' variables.
        """
        
        response = await self.llm.complete(
            messages=[{"role": "system", "content": "You are the OMNIOS SELF-CODER."},
                      {"role": "user", "content": prompt}],
            task_type="reasoning"
        )
        
        # In a real environment, we'd validate the code first.
        # For PoC, we write it to the fabric.
        with open(target_path, "w") as f:
            f.write(response["content"])
            
        print(f"[EVO] Created new autonomous tool: {target_path}")
        return target_path
