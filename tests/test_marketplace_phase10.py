import asyncio
import os
import shutil
import json
from marketplace.registry import PluginRegistry

async def test_marketplace():
    base_dir = "./test_data_marketplace"
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    
    os.makedirs(base_dir)
    registry = PluginRegistry(base_dir)

    print("--- Testing Plugin Installation ---")
    # Create a dummy plugin file
    dummy_source = os.path.join(base_dir, "new_agent_source.py")
    with open(dummy_source, "w") as f:
        f.write("def run(): print('Hello from Plugin')")

    plugin_data = {
        "name": "research_agent",
        "version": "1.0.0",
        "author": "CommunityUser",
        "description": "Scrapes the web for data.",
        "entry_point": "research_agent.py"
    }
    
    registry.install_plugin(plugin_data, dummy_source)
    
    plugins = registry.list_plugins()
    print(f"Installed Plugins: {plugins}")
    
    if len(plugins) == 1 and plugins[0]["name"] == "research_agent":
        print("PASS: Plugin installed correctly")
    else:
        print("FAIL: Plugin installation failed")

    print("\n--- Testing Discovery ---")
    ep = registry.get_plugin_entry_point("research_agent")
    print(f"Entry Point: {ep}")
    
    if ep and os.path.exists(ep):
        print("PASS: Plugin entry point discovered")
    else:
        print("FAIL: Entry point invalid")

    print("\n--- Testing Uninstallation ---")
    registry.uninstall_plugin("research_agent")
    if len(registry.list_plugins()) == 0:
        print("PASS: Plugin uninstalled correctly")
    else:
        print("FAIL: Uninstallation failed")

    # Clean up
    shutil.rmtree(base_dir)

if __name__ == "__main__":
    asyncio.run(test_marketplace())
