import asyncio
import yaml
import logging
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from core.coordinator import CoordinatorAgent
from core.autonomous_loop import AutonomousLoop
from agents.system_agent import SystemAgent

from utils.logger import setup_logging

# Setup Logging
logger = setup_logging()

def load_config() -> dict:
    load_dotenv()
    config_path = "config/settings.yaml"
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        return {}
        
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Resolve environment variables
    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]
            return os.getenv(env_var, "")
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(v) for v in obj]
        return obj

    return resolve_env(config)

async def main():
    logger.info("""
      ___  __  __ _  _ ___ ___  ___   _   _  ____      ____ 
     / _ \|  \/  | \| |_ _/ _ \/ __| | | | ||__ /  _  |__  |
    | (_) | |\/| | .` || | (_) \__ \ | |_| | |_ \ (_)   / / 
     \___/|_|  |_|_|\_|___\___/|___/  \___/ |___/     /_/  
    
    [OMNIOS] v3.0 - Autonomous Multi-Agent System
    """)
    
    config = load_config()
    if not config:
        logger.error("Failed to load configuration. Exiting.")
        return

    logger.info("🚀 Starting OMNIOS v3.0")
    logger.info(f"   Configured providers: {list(config.get('providers', {}).keys())}")

    # Initialize coordinator
    coordinator = CoordinatorAgent(config)
    logger.info("   ✅ Coordinator Agent initialized")

    # Register agents
    agents_config = config.get("agents", {})

    # Register System Agent (Core capability)
    if agents_config.get("system", {}).get("enabled"):
        system_agent = SystemAgent(config, "system_agent")
        coordinator.register_agent(system_agent)
        logger.info("   ✅ System Agent registered")

    # Initialize autonomous loop
    autonomous = AutonomousLoop(coordinator, config)

    # Start services
    tasks = []

    # Autonomous loop
    if config.get("autonomous", {}).get("enabled"):
        tasks.append(autonomous.start())
        logger.info("   ✅ Autonomous Loop started")

    logger.info("=" * 60)
    logger.info("🤖 OMNIOS v3.0 is fully operational")
    logger.info("=" * 60)
    
    # Process initial test input if provided interactively
    # In a real deployment this would wait for API/CLI input
    # For now, we simulate a keep-alive
    
    try:
        while True:
            await asyncio.sleep(1)
            # checking for keyboard interrupt to exit?
            # actually we should just await the tasks
            if not tasks:
                 break
            # await asyncio.gather(*tasks) # This would block immediate interaction
    except KeyboardInterrupt:
        await autonomous.stop()
        logger.info("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())
