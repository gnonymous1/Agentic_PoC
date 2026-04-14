"""
Identity Loader - OpenClaw-style identity file management
Loads and injects SOUL.md, IDENTITY.md, MEMORY.md, HEARTBEAT.md into prompts
"""

import os
from pathlib import Path
from typing import Dict, Optional
from utils.logger import setup_logging

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    Observer = None
    FileSystemEventHandler = object

logger = setup_logging()


class IdentityLoader:
    """Loads identity files from workspace directory and injects into prompts"""
    
    def __init__(self, workspace_path: str = "./workspace"):
        self.workspace = Path(workspace_path)
        self._cache: Dict[str, str] = {}
        self._watcher: Optional[Observer] = None
        self._load_all()
    
    def _load_all(self):
        """Load all identity files into cache"""
        identity_files = {
            "SOUL": "SOUL.md",
            "IDENTITY": "IDENTITY.md", 
            "MEMORY": "MEMORY.md",
            "HEARTBEAT": "HEARTBEAT.md"
        }
        
        for key, filename in identity_files.items():
            filepath = self.workspace / filename
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self._cache[key] = f.read()
                    logger.info(f"[Identity] Loaded {filename}")
                except Exception as e:
                    logger.error(f"[Identity] Failed to load {filename}: {e}")
                    self._cache[key] = ""
            else:
                self._cache[key] = ""
                logger.warning(f"[Identity] {filename} not found")
    
    def get(self, key: str) -> str:
        """Get a specific identity file content"""
        return self._cache.get(key.upper(), "")
    
    def get_soul(self) -> str:
        """Get SOUL.md content"""
        return self.get("SOUL")
    
    def get_identity(self) -> str:
        """Get IDENTITY.md content"""
        return self.get("IDENTITY")
    
    def get_memory(self) -> str:
        """Get MEMORY.md content"""
        return self.get("MEMORY")
    
    def get_heartbeat(self) -> str:
        """Get HEARTBEAT.md content"""
        return self.get("HEARTBEAT")
    
    def inject_into_prompt(self, base_prompt: str) -> str:
        """
        Inject identity files into a system prompt
        Returns combined prompt with identity context
        """
        sections = []
        
        # Add SOUL (core personality)
        soul = self.get_soul()
        if soul:
            sections.append(f"## Core Personality\n{soul}\n")
        
        # Add IDENTITY (role and capabilities)
        identity = self.get_identity()
        if identity:
            sections.append(f"## Identity\n{identity}\n")
        
        # Add MEMORY (context)
        memory = self.get_memory()
        if memory:
            sections.append(f"## Context\n{memory}\n")
        
        # Combine with base prompt
        if sections:
            return f"{base_prompt}\n\n" + "\n".join(sections)
        return base_prompt
    
    def reload(self):
        """Reload all identity files from disk"""
        logger.info("[Identity] Reloading identity files...")
        self._cache.clear()
        self._load_all()
    
    def start_watching(self):
        """Start file watcher for auto-reload (optional)"""
        if Observer is None:
            logger.warning("[Identity] watchdog is not installed. Skipping file watcher startup.")
            return

        if self._watcher is not None:
            return
        
        class IdentityHandler(FileSystemEventHandler):
            def __init__(self, loader):
                self.loader = loader
            
            def on_modified(self, event):
                if event.src_path.endswith(('.md', '.txt')):
                    logger.info(f"[Identity] File modified: {event.src_path}")
                    self.loader.reload()
        
        self._watcher = Observer()
        handler = IdentityHandler(self)
        self._watcher.schedule(handler, str(self.workspace), recursive=True)
        self._watcher.start()
        logger.info("[Identity] Started file watcher")
    
    def stop_watching(self):
        """Stop file watcher"""
        if self._watcher:
            self._watcher.stop()
            self._watcher.join()
            self._watcher = None
            logger.info("[Identity] Stopped file watcher")


# Global instance
_identity_loader: Optional[IdentityLoader] = None


def get_identity_loader() -> IdentityLoader:
    """Get global identity loader instance"""
    global _identity_loader
    if _identity_loader is None:
        _identity_loader = IdentityLoader()
    return _identity_loader


def inject_identity(prompt: str) -> str:
    """Convenience function to inject identity into a prompt"""
    loader = get_identity_loader()
    return loader.inject_into_prompt(prompt)
