import json
import os
import shutil
from typing import List, Dict, Any, Optional

class MarketplacePlugin:
    def __init__(self, name: str, version: str, author: str, description: str, entry_point: str):
        self.name = name
        self.version = version
        self.author = author
        self.description = description
        self.entry_point = entry_point

class PluginRegistry:
    """
    Manages the installation and discovery of community agents/tools.
    """

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.plugins_dir = os.path.join(base_dir, "installed_plugins")
        self.manifest_path = os.path.join(self.plugins_dir, "manifest.json")
        self._ensure_paths()
        self.plugins = self._load_manifest()

    def _ensure_paths(self):
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
        if not os.path.exists(self.manifest_path):
            with open(self.manifest_path, "w") as f:
                json.dump({}, f)

    def _load_manifest(self) -> Dict[str, dict]:
        with open(self.manifest_path, "r") as f:
            return json.load(f)

    def _save_manifest(self):
        with open(self.manifest_path, "w") as f:
            json.dump(self.plugins, f, indent=4)

    def install_plugin(self, plugin_data: dict, source_path: str):
        """Simulate installing a plugin from a source file."""
        name = plugin_data["name"]
        dest_path = os.path.join(self.plugins_dir, f"{name}.py")
        
        # Copy file
        shutil.copy(source_path, dest_path)
        
        # Update manifest
        self.plugins[name] = plugin_data
        self._save_manifest()
        return True

    def uninstall_plugin(self, name: str):
        """Remove a plugin and update manifest."""
        if name in self.plugins:
            plugin_path = os.path.join(self.plugins_dir, f"{name}.py")
            if os.path.exists(plugin_path):
                os.remove(plugin_path)
            del self.plugins[name]
            self._save_manifest()
            return True
        return False

    def list_plugins(self) -> List[dict]:
        """Return all installed plugins."""
        return list(self.plugins.values())

    def get_plugin_entry_point(self, name: str) -> Optional[str]:
        """Return the entry point (filename) for an agent."""
        if name in self.plugins:
            return os.path.join(self.plugins_dir, f"{name}.py")
        return None
