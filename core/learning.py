import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.memory import VectorMemory

class AdaptiveLearningEngine:
    """
    Learns from user interactions to improve system behavior.
    Tracks preferences, success rates, and refines prompts.
    """

    def __init__(self, config: dict, memory: Optional[VectorMemory] = None):
        self.config = config
        self.memory = memory or VectorMemory(config)
        self.user_preferences: Dict[str, Any] = {}
        self.strategy_success_rates: Dict[str, float] = {}

    async def learn_from_interaction(self, user_input: str, response: str, feedback: Optional[dict] = None, task_type: str = "general"):
        """Analyze an interaction to extract learnings."""
        # 1. Store the interaction
        await self.memory.store({
            "type": "interaction_learning",
            "task_type": task_type,
            "input": user_input,
            "response": response,
            "feedback": feedback,
            "timestamp": datetime.now().isoformat()
        }, collection="learnings")

        # 2. Extract preferences
        if feedback:
            await self._update_preferences(user_input, response, feedback, task_type)

    async def _update_preferences(self, user_input: str, response: str, feedback: dict, task_type: str):
        # Store feedback as a behavioral pattern with searchable metadata
        await self.memory.store({
            "type": "behavioral_pattern",
            "task_type": task_type,
            "tags": ["user_preference", "style_guide", task_type],
            "pattern": feedback.get("comment", ""),
            "rating": feedback.get("rating", 0),
            "timestamp": datetime.now().isoformat()
        }, collection="patterns")

    async def get_refined_prompt(self, base_prompt: str, task_type: str) -> str:
        """Apply learned preferences to a prompt."""
        # 1. Search for relevant behavioral patterns
        patterns = await self.memory.search(f"User preferences for {task_type}", limit=3, collection="patterns")
        
        if not patterns:
            return base_prompt

        # 2. Augment prompt with patterns
        refinements = [p["data"].get("pattern") for p in patterns if p["relevance"] > 0.7]
        if refinements:
            style_guide = "\nUSER PREFERENCES:\n- " + "\n- ".join(refinements)
            return base_prompt + style_guide
        
        return base_prompt

class PromptRefiner:
    """Auto-optimizes prompts based on past successes/failures."""
    
    def __init__(self, learning_engine: AdaptiveLearningEngine):
        self.learning = learning_engine

    async def optimize(self, prompt: str, task_context: dict) -> str:
        # Simplified: appends success-based directives
        return await self.learning.get_refined_prompt(prompt, task_context.get("type", "general"))
