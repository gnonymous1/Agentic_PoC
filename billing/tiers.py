from enum import Enum
from typing import Dict, Any

class ServiceTier(Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class QuotaLimits:
    def __init__(self, daily_tokens: int, max_parallel_tasks: int, premium_agents: bool):
        self.daily_tokens = daily_tokens
        self.max_parallel_tasks = max_parallel_tasks
        self.premium_agents = premium_agents

TIER_CONFIGS = {
    ServiceTier.FREE: QuotaLimits(daily_tokens=10000, max_parallel_tasks=2, premium_agents=False),
    ServiceTier.PRO: QuotaLimits(daily_tokens=500000, max_parallel_tasks=10, premium_agents=True),
    ServiceTier.ENTERPRISE: QuotaLimits(daily_tokens=-1, max_parallel_tasks=100, premium_agents=True), # -1 for unlimited
}

class UsageQuotaManager:
    """
    Manages usage limits and service tiers for users/accounts.
    """

    def __init__(self):
        self.user_tiers: Dict[str, ServiceTier] = {}
        self.usage_counters: Dict[str, dict] = {}

    def set_user_tier(self, user_id: str, tier: ServiceTier):
        self.user_tiers[user_id] = tier
        if user_id not in self.usage_counters:
            self.usage_counters[user_id] = {"tokens_used": 0, "active_tasks": 0}

    def check_quota(self, user_id: str, action_type: str, amount: int = 1) -> bool:
        """Check if an action is within the user's quota."""
        tier = self.user_tiers.get(user_id, ServiceTier.FREE)
        config = TIER_CONFIGS[tier]
        counters = self.usage_counters.get(user_id, {"tokens_used": 0, "active_tasks": 0})

        if action_type == "tokens":
            if config.daily_tokens == -1: return True
            return (counters["tokens_used"] + amount) <= config.daily_tokens
        
        if action_type == "parallel_tasks":
            return counters["active_tasks"] < config.max_parallel_tasks

        return True

    def record_usage(self, user_id: str, action_type: str, amount: int = 1):
        """Log usage against a user's quota."""
        if user_id not in self.usage_counters:
            self.usage_counters[user_id] = {"tokens_used": 0, "active_tasks": 0}
        
        if action_type == "tokens":
            self.usage_counters[user_id]["tokens_used"] += amount
        elif action_type == "task_start":
            self.usage_counters[user_id]["active_tasks"] += 1
        elif action_type == "task_end":
            self.usage_counters[user_id]["active_tasks"] = max(0, self.usage_counters[user_id]["active_tasks"] - 1)

    def get_user_stats(self, user_id: str) -> dict:
        tier = self.user_tiers.get(user_id, ServiceTier.FREE)
        return {
            "tier": tier.value,
            "usage": self.usage_counters.get(user_id, {}),
            "limits": {
                "daily_tokens": TIER_CONFIGS[tier].daily_tokens,
                "parallel_tasks": TIER_CONFIGS[tier].max_parallel_tasks
            }
        }
