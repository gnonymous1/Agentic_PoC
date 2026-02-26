import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

class RewardModel:
    """
    Tracks and calculates rewards for agent actions.
    Simple Q-Learning inspired approach: Key = (Role, Tool), Value = Score.
    """
    def __init__(self, storage_path: str = "data/rl_weights.json"):
        self.storage_path = storage_path
        self.weights: Dict[str, float] = self._load_weights()
        self.history: List[Dict] = []
        
        # Hyperparameters
        self.learning_rate = 0.1
        self.discount_factor = 0.9

    def _load_weights(self) -> Dict[str, float]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except:
                return {}
        return defaultdict(float)

    def save_weights(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self.weights, f, indent=2)

    def update_reward(self, role: str, tool_name: str, outcome: str, reward_value: float = None):
        """
        Update the weight for a specific (Role, Tool) pair based on outcome.
        - success: +1.0
        - failure: -1.0
        """
        key = f"{role}:{tool_name}"
        
        if reward_value is None:
            if outcome == "success":
                reward_value = 1.0
            elif outcome == "failure":
                reward_value = -1.0
            else:
                reward_value = 0.0

        # Simple update rule: New = Old + LR * (Reward - Old)
        current_weight = self.weights.get(key, 0.0)
        new_weight = current_weight + self.learning_rate * (reward_value - current_weight)
        self.weights[key] = new_weight
        
        # Log history
        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "tool": tool_name,
            "outcome": outcome,
            "reward": reward_value,
            "new_weight": new_weight
        })
        
        self.save_weights()
        print(f"[RL] Updated weight for {key}: {current_weight:.2f} -> {new_weight:.2f}")

    def get_tool_score(self, role: str, tool_name: str) -> float:
        """Get the current learned score for a tool."""
        return self.weights.get(f"{role}:{tool_name}", 0.0)

# Global Instance
learning_engine = RewardModel()
