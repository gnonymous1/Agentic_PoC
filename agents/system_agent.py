import asyncio
import platform
import subprocess
import os
from typing import List, Dict, Any
from agents.base_agent import BaseAgent, SubAgentTask

# Import existing tool functions we created in Phase 8
# We'll wrap these into the new agent structure
from agent_fabric.computer_tools import (
    system_get_clipboard, system_set_clipboard,
    system_get_volume, system_set_volume,
    system_get_display_info, computer_screenshot
)

class SystemAgent(BaseAgent):
    """
    Agent responsible for OS-level operations:
    - Clipboard management
    - Volume/Display control
    - Screenshots
    - File system navigation (future)
    """

    def _register_sub_agents(self):
        """Register system capabilities."""
        
        # Clipboard Sub-Agent
        self.sub_agents["clipboard_manager"] = SubAgentTask(
            name="clipboard_manager",
            handler=self._handle_clipboard,
            description="Manage system clipboard",
            capabilities=["get_clipboard", "set_clipboard"]
        )

        # Media Sub-Agent
        self.sub_agents["media_controller"] = SubAgentTask(
            name="media_controller",
            handler=self._handle_media,
            description="Control volume and display",
            capabilities=["get_volume", "set_volume", "get_display_info"]
        )
        
        # Screen Sub-Agent
        self.sub_agents["screen_capture"] = SubAgentTask(
            name="screen_capture",
            handler=self._handle_screen,
            description="Capture screen content",
            capabilities=["take_screenshot"]
        )

    def get_capabilities(self) -> List[str]:
        caps = []
        for sa in self.sub_agents.values():
            caps.extend(sa.capabilities)
        return caps

    async def _handle_clipboard(self, params: dict) -> dict:
        action = params.get("action")
        if action == "get_clipboard":
            # Call existing tool (wrapped in sync-to-async if needed)
            # system_get_clipboard is a synchronous tool function
            content = system_get_clipboard()
            return {"status": "success", "content": content}
        
        elif action == "set_clipboard":
            text = params.get("text", "")
            result = system_set_clipboard(text)
            return {"status": "success", "message": result}
            
        return {"status": "error", "message": "Unknown clipboard action"}

    async def _handle_media(self, params: dict) -> dict:
        action = params.get("action")
        
        if action == "get_volume":
            # computer_tools doesn't strictly have a get_volume that returns int, 
            # but we can implement/mock it or use what's there.
            # system_get_volume in computer_tools returned info string.
            return {"status": "success", "info": system_get_volume()}
            
        elif action == "set_volume":
            level = int(params.get("level", 50))
            result = system_set_volume(level)
            return {"status": "success", "message": result}
            
        elif action == "get_display_info":
            result = system_get_display_info()
            return {"status": "success", "info": result}

        return {"status": "error", "message": "Unknown media action"}

    async def _handle_screen(self, params: dict) -> dict:
        # Check if requested action matches
        # The execute() method routes by action name, so we know it's take_screenshot
        filename = params.get("filename", "screenshot.png")
        result = computer_screenshot(filename)
        return {"status": "success", "message": result, "path": filename}
