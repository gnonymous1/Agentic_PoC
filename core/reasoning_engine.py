import asyncio
import json
from typing import List, Dict, Any, Optional
from core.llm_router import LLMRouter

class AdvancedReasoningEngine:
    """
    Implements complex reasoning patterns:
    1. Tree of Thoughts (ToT)
    2. Self-Reflection
    3. Multi-Model Consensus
    """

    def __init__(self, llm_router: LLMRouter):
        self.llm = llm_router

    async def reason_with_reflection(self, prompt: str, iterations: int = 1) -> str:
        """Reason -> Critique -> Refine loop."""
        # Initial thought
        response = await self.llm.complete([{"role": "user", "content": prompt}], task_type="reasoning")
        thought = response["content"]

        for i in range(iterations):
            # Reflection
            critique_prompt = f"Critique this response for accuracy and completeness. Identify errors or missing info:\n\n{thought}"
            critique_res = await self.llm.complete([{"role": "user", "content": critique_prompt}], task_type="reasoning")
            critique = critique_res["content"]

            # Refinement
            refine_prompt = f"Refine the original response based on this critique:\nOriginal: {thought}\nCritique: {critique}\nNew Version:"
            refine_res = await self.llm.complete([{"role": "user", "content": refine_prompt}], task_type="reasoning")
            thought = refine_res["content"]

        return thought

    async def reason_tree_of_thoughts(self, problem: str, num_thoughts: int = 3) -> str:
        """Explore multiple reasoning paths and choose the best."""
        # Step 1: Generate multiple initial thoughts
        gen_prompt = f"Propose {num_thoughts} different approaches to solve this problem: {problem}\nSeparate with ---"
        gen_res = await self.llm.complete([{"role": "user", "content": gen_prompt}], task_type="reasoning")
        thoughts = gen_res["content"].split("---")

        # Step 2: Evaluate thoughts
        eval_prompt = f"Evaluate these different thoughts and identify which is most likely to be correct/optimal. Justify your choice and provide the final answer based on that choice.\n\nThoughts:\n"
        for i, t in enumerate(thoughts):
            eval_prompt += f"Thought {i+1}: {t.strip()}\n"
        
        final_res = await self.llm.complete([{"role": "user", "content": eval_prompt}], task_type="reasoning")
        return final_res["content"]

    async def reach_consensus(self, prompt: str, providers: List[str]) -> str:
        """Run the same prompt on multiple models and aggregate."""
        tasks = []
        for provider in providers:
            tasks.append(self.llm.complete([{"role": "user", "content": prompt}], provider=provider, task_type="reasoning"))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        responses = []
        for res in results:
            if not isinstance(res, Exception):
                responses.append(res["content"])
        
        # Aggregate consensus
        agg_prompt = f"Compare these different AI responses and synthesize the most accurate consensus answer:\n\n"
        for i, r in enumerate(responses):
            agg_prompt += f"Response {i+1}: {r}\n"
            
        final_res = await self.llm.complete([{"role": "user", "content": agg_prompt}], task_type="reasoning")
        return final_res["content"]
