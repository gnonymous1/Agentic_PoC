import asyncio
import logging
from datetime import datetime, timedelta
from core.coordinator import CoordinatorAgent
# We can reuse the workflow engine from previous phases if compatible, 
# or stub it for now until full integration.
# form core.workflow_engine import WorkflowEngine 

logger = logging.getLogger("omnios.autonomous")

class AutonomousLoop:
    """
    The always-running brain that:
    1. Runs scheduled workflows
    2. Thinks autonomously about what to do
    3. Monitors for events/triggers
    4. Self-improves periodically
    """

    def __init__(
        self,
        coordinator: CoordinatorAgent,
        config: dict,
    ):
        self.coordinator = coordinator
        self.config = config
        self.running = False
        self.last_autonomous_think = None
        self.think_interval = config.get("autonomous", {}).get(
            "think_interval_seconds", 300
        )
        self.last_self_improve = None
        self.self_improve_interval = 3600 * 6  # Every 6 hours

    async def start(self):
        """Start the autonomous loop."""
        self.running = True
        logger.info("🧠 Autonomous loop started")

        # In a real app, these would be separate tasks. 
        # For PoC, we'll run a single loop that checks everything.
        asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        logger.info("🧠 Autonomous loop stopped")

    async def _main_loop(self):
        while self.running:
            await self._autonomous_thinking_step()
            await self._self_improvement_step()
            await asyncio.sleep(10) # Tick every 10s

    async def _autonomous_thinking_step(self):
        """Periodically think about what to do proactively."""
        try:
            now = datetime.now()
            if (
                self.last_autonomous_think is None or
                (now - self.last_autonomous_think).seconds > self.think_interval
            ):
                # Call Coordinator to think
                decision = await self.coordinator.autonomous_think()
                self.last_autonomous_think = now

                if decision and decision.get("should_act"):
                    logger.info(f"🤖 Auto-executing action: {decision}")
                    # In real impl, we would execute the action here
        except Exception as e:
            logger.error(f"Autonomous thinking error: {e}")

    async def _self_improvement_step(self):
        """Periodically improve prompts and strategies."""
        try:
            now = datetime.now()
            if (
                self.last_self_improve is None or
                (now - self.last_self_improve).seconds > self.self_improve_interval
            ):
                logger.info("🧬 Running self-improvement cycle")
                improvements = await self.coordinator.self_improver.self_improve_prompts()
                self.last_self_improve = now
                if improvements:
                    logger.info(f"🧬 Found potential improvements: {improvements}")
        except Exception as e:
            logger.error(f"Self-improvement error: {e}")
