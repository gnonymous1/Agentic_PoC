import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from cortex.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

@dataclass
class WorkflowTemplate:
    id: str
    name: str
    description: str
    category: str
    steps: List[Dict[str, Any]]
    tags: List[str]

class WorkflowRegistry:
    """Manages a library of reusable workflows."""

    def __init__(self, data_dir: str = "data/workflows"):
        self.data_dir = data_dir
        self.workflows: Dict[str, WorkflowTemplate] = {}
        os.makedirs(data_dir, exist_ok=True)
        self._load_workflows()

    def _load_workflows(self):
        """Loads workflows from JSON files."""
        if not os.path.exists(self.data_dir): return

        for filename in os.listdir(self.data_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.data_dir, filename), 'r') as f:
                        data = json.load(f)
                        wf = WorkflowTemplate(**data)
                        self.workflows[wf.id] = wf
                except Exception as e:
                    print(f"Error loading workflow {filename}: {e}")

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowTemplate]:
        return self.workflows.get(workflow_id)

    def list_workflows(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists workflows, optionally filtered by category."""
        return [asdict(wf) for wf in self.workflows.values() if not category or wf.category == category]

    def save_workflow(self, workflow: WorkflowTemplate):
        """Saves a workflow to disk."""
        self.workflows[workflow.id] = workflow
        filepath = os.path.join(self.data_dir, f"{workflow.id}.json")
        with open(filepath, 'w') as f:
            json.dump(asdict(workflow), f, indent=2)

class WorkflowGenerator:
    """Generates synthetic workflows using LLM."""

    def __init__(self, registry: WorkflowRegistry):
        self.registry = registry
        self.llm = get_llm(role="architect")

    def generate_presets(self, count: int = 10):
        """Generates a set of diverse workflow presets."""
        categories = ["System Admin", "Development", "Research", "Security", "Data Analysis"]

        prompt = f"""Generate {count} distinct, professional workflow templates for an autonomous agent system.
Available Tools: git_clone, execute_python, vector_search, web_scrape, system_info, ping_host, list_files.
Categories: {', '.join(categories)}.

Output a JSON object with a key "workflows" containing a list of objects.
Each object must have:
- id: unique string (e.g., "sys_audit_01")
- name: Display name
- description: Purpose
- category: One of the categories above
- tags: List of keywords
- steps: List of objects {{"agent": "Operator|Coder|Researcher", "tool": "tool_name", "params": {{...}}}}

Ensure the workflows are logical and varied."""

        try:
            response = self.llm.invoke([SystemMessage(content="You are a System Architect."), HumanMessage(content=prompt)])
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content)
            for wf_data in data.get("workflows", []):
                wf = WorkflowTemplate(**wf_data)
                self.registry.save_workflow(wf)

            print(f"Generated {len(data.get('workflows', []))} workflows.")

        except Exception as e:
            print(f"Workflow generation failed: {e}")
            # Fallback seed
            self._seed_defaults()

    def _seed_defaults(self):
        """Fallback to seed basic workflows if LLM fails."""
        default = WorkflowTemplate(
            id="basic_health_check",
            name="System Health Check",
            description="Checks system vital stats.",
            category="System Admin",
            tags=["health", "maintenance"],
            steps=[
                {"agent": "Operator", "tool": "system_info", "params": {}},
                {"agent": "Operator", "tool": "list_files_recursive", "params": {"path": "/var/log"}}
            ]
        )
        self.registry.save_workflow(default)

# Global Instance
workflow_registry = WorkflowRegistry()
workflow_generator = WorkflowGenerator(workflow_registry)
