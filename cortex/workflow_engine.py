"""
Workflow Execution Engine
Parses and executes multi-step workflow definitions with advanced features.
"""

import yaml
import json
import os
import asyncio
from typing import Dict, List, Any, Optional, Callable, Set
from cortex.state import AgentState
from langchain_core.messages import HumanMessage
from concurrent.futures import ThreadPoolExecutor
from cortex.graph import graph

class WorkflowEngine:
    """
    Executes structured workflows with dependency management, parallel execution, and advanced features.
    """
    
    def __init__(self, graph):
        """
        Initialize workflow engine with agent graph.
        
        Args:
            graph: The compiled LangGraph agent graph
        """
        self.graph = graph
        self.workflows_dir = "workflows"
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running_workflows = {}
    
    def load_workflow(self, workflow_name: str) -> Dict[str, Any]:
        """
        Load a workflow definition from file.
        
        Args:
            workflow_name: Name of the workflow (without extension)
            
        Returns:
            Parsed workflow definition
        """
        filepath = os.path.join(self.workflows_dir, f"{workflow_name}.yaml")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Workflow not found: {workflow_name}")
        
        with open(filepath, 'r') as f:
            workflow = yaml.safe_load(f)
        
        return workflow
    
    def list_workflows(self) -> List[Dict[str, str]]:
        """
        List all available workflows.
        
        Returns:
            List of workflow metadata
        """
        if not os.path.exists(self.workflows_dir):
            return []
        
        workflows = []
        for filename in os.listdir(self.workflows_dir):
            if filename.endswith('.yaml'):
                try:
                    workflow = self.load_workflow(filename[:-5])
                    workflows.append({
                        "name": workflow.get("name", filename),
                        "description": workflow.get("description", "No description"),
                        "filename": filename,
                        "steps": len(workflow.get("steps", [])),
                        "dependencies": self._extract_dependencies(workflow)
                    })
                except:
                    pass
        
        return workflows
    
    def _extract_dependencies(self, workflow: Dict[str, Any]) -> List[str]:
        """Extract all dependencies from workflow steps."""
        dependencies = set()
        for step in workflow.get("steps", []):
            if "depends_on" in step:
                if isinstance(step["depends_on"], list):
                    dependencies.update(step["depends_on"])
                else:
                    dependencies.add(step["depends_on"])
        
        return sorted(dependencies)
    
    async def execute_workflow(self, workflow_name: str, variables: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Execute a workflow with dependency management and parallel execution.
        
        Args:
            workflow_name: Name of the workflow to execute
            variables: Variable substitutions for the workflow
            
        Returns:
            Execution result with status and log
        """
        workflow = self.load_workflow(workflow_name)
        steps = workflow.get("steps", [])
        variables = variables or {}
        
        # Build step dependency graph
        dependency_graph = self._build_dependency_graph(steps)
        
        # Get execution order (topological sort)
        execution_order = self._topological_sort(dependency_graph)
        
        log = [f"Starting workflow: {workflow.get('name', workflow_name)}"]
        results = {}
        
        # Execute steps in parallel where possible
        await self._execute_steps_in_parallel(
            steps, execution_order, variables, results, log
        )
        
        log.append("Workflow execution complete.")
        
        return {
            "status": "success",
            "workflow_name": workflow_name,
            "total_steps": len(steps),
            "completed_steps": len([r for r in results.values() if r.get("status") == "success"]),
            "log": log,
            "results": results
        }
    
    def _build_dependency_graph(self, steps: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
        """Build dependency graph from workflow steps."""
        graph = {}
        
        for idx, step in enumerate(steps):
            step_id = str(idx + 1)
            dependencies = set()
            
            if "depends_on" in step:
                if isinstance(step["depends_on"], list):
                    dependencies.update(step["depends_on"])
                else:
                    dependencies.add(step["depends_on"])
            
            graph[step_id] = dependencies
        
        return graph
    
    def _topological_sort(self, graph: Dict[str, Set[str]]) -> List[str]:
        """Perform topological sort on dependency graph."""
        in_degree = {node: 0 for node in graph}
        
        for node in graph:
            for neighbor in graph[node]:
                in_degree[neighbor] += 1
        
        queue = [node for node in graph if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph:
                if node in graph[neighbor]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
        
        if len(result) != len(graph):
            raise ValueError("Workflow has circular dependencies")
        
        return result
    
    async def _execute_steps_in_parallel(
        self,
        steps: List[Dict[str, Any]],
        execution_order: List[str],
        variables: Dict[str, str],
        results: Dict[str, Any],
        log: List[str]
    ):
        """Execute workflow steps in parallel where possible."""
        completed_steps = set()
        
        async def execute_step(step_id: str):
            """Execute a single step."""
            step = steps[int(step_id) - 1]
            agent = step.get("agent", "Operator")
            action = step.get("action", "unknown")
            params = step.get("params", {})
            
            # Variable substitution
            for key, value in params.items():
                if isinstance(value, str) and "{{" in value:
                    for var_name, var_value in variables.items():
                        value = value.replace(f"{{{{{var_name}}}}}", str(var_value))
                    params[key] = value
            
            log.append(f"Executing step {step_id}: {agent}.{action}({params})")
            
            # Build message for this step
            state = AgentState(messages=[
                HumanMessage(content=f"Executing workflow step {step_id}: {action} with params {json.dumps(params)}")
            ])
            
            try:
                # Execute step via graph
                result = await self.graph.ainvoke(state)
                
                # Extract result from state
                result_content = result["messages"][-1].content if result["messages"] else "Success"
                
                results[step_id] = {
                    "status": "success",
                    "agent": agent,
                    "action": action,
                    "params": params,
                    "result": result_content
                }
                
                log.append(f"Step {step_id} completed successfully")
                
            except Exception as e:
                results[step_id] = {
                    "status": "error",
                    "agent": agent,
                    "action": action,
                    "params": params,
                    "error": str(e)
                }
                
                log.append(f"Step {step_id} failed: {e}")
                raise
            
            finally:
                completed_steps.add(step_id)
        
        # Execute steps in parallel respecting dependencies
        for step_id in execution_order:
            # Wait for dependencies to complete
            dependencies = self._build_dependency_graph(steps)[step_id]
            while not dependencies.issubset(completed_steps):
                await asyncio.sleep(0.1)
            
            # Execute step
            await execute_step(step_id)
    
    async def execute_workflow_with_monitoring(
        self, workflow_name: str, variables: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Execute workflow with real-time monitoring and progress tracking.
        
        Args:
            workflow_name: Name of the workflow to execute
            variables: Variable substitutions for the workflow
            
        Returns:
            Execution result with monitoring data
        """
        import time
        
        start_time = time.time()
        
        # Start workflow execution
        execution_task = asyncio.create_task(
            self.execute_workflow(workflow_name, variables)
        )
        
        # Monitor progress
        progress = {
            "total_steps": 0,
            "completed_steps": 0,
            "current_step": None,
            "status": "running",
            "start_time": start_time,
            "elapsed_time": 0
        }
        
        while not execution_task.done():
            # Update progress
            result = execution_task.result() if execution_task.done() else None
            
            if result:
                progress["total_steps"] = result.get("total_steps", 0)
                progress["completed_steps"] = result.get("completed_steps", 0)
                progress["status"] = result.get("status", "completed")
                progress["elapsed_time"] = time.time() - start_time
            
            await asyncio.sleep(0.5)
        
        # Get final result
        final_result = await execution_task
        progress.update(final_result)
        
        return progress
    
    def save_workflow(self, workflow_name: str, workflow_def: Dict[str, Any]):
        """
        Save a workflow definition to file.
        
        Args:
            workflow_name: Name for the workflow file
            workflow_def: Workflow definition dictionary
        """
        if not os.path.exists(self.workflows_dir):
            os.makedirs(self.workflows_dir)
        
        filepath = os.path.join(self.workflows_dir, f"{workflow_name}.yaml")
        
        with open(filepath, 'w') as f:
            yaml.dump(workflow_def, f, default_flow_style=False)
    
    def validate_workflow(self, workflow_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate workflow definition for errors and issues.
        
        Args:
            workflow_def: Workflow definition to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Check required fields
        if "name" not in workflow_def:
            errors.append("Missing required field: 'name'")
        if "steps" not in workflow_def:
            errors.append("Missing required field: 'steps'")
        
        # Validate steps
        step_ids = set()
        dependencies = set()
        
        for idx, step in enumerate(workflow_def.get("steps", [])):
            step_id = str(idx + 1)
            step_ids.add(step_id)
            
            # Check required step fields
            if "agent" not in step:
                errors.append(f"Step {step_id} missing required field: 'agent'")
            if "action" not in step:
                errors.append(f"Step {step_id} missing required field: 'action'")
            
            # Check dependencies
            if "depends_on" in step:
                deps = step["depends_on"]
                if isinstance(deps, list):
                    for dep in deps:
                        if dep not in step_ids and dep != "start":
                            errors.append(f"Step {step_id} depends on non-existent step: {dep}")
                        dependencies.add(dep)
                else:
                    if deps not in step_ids and deps != "start":
                        errors.append(f"Step {step_id} depends on non-existent step: {deps}")
                    dependencies.add(deps)
        
        # Check for circular dependencies
        try:
            self._topological_sort(self._build_dependency_graph(workflow_def.get("steps", [])))
        except ValueError:
            errors.append("Workflow contains circular dependencies")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

# Script execution with enhanced security
class ScriptExecutor:
    """
    Executes user-defined scripts with sandboxing and security controls.
    """
    
    def __init__(self):
        self.scripts_dir = "scripts"
        self.safe_modules = [
            "json", "yaml", "datetime", "time", "math", "random", "re",
            "string", "collections", "itertools", "functools", "typing"
        ]

    def _validate_python_script(self, script_content: str):
        """Validates Python script for security issues using AST."""
        import ast
        try:
            tree = ast.parse(script_content)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in script: {e}")

        for node in ast.walk(tree):
            # Prevent access to private/special attributes (e.g., __class__, __subclasses__)
            if isinstance(node, ast.Attribute):
                if node.attr.startswith('__'):
                    raise ValueError(f"Security violation: Access to private attribute '{node.attr}' is forbidden")

            # Prevent dangerous built-in calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    forbidden_calls = [
                        'eval', 'exec', 'getattr', 'setattr', 'delattr', 'input',
                        'breakpoint', 'globals', 'locals', 'vars', 'help', 'dir',
                        'id', 'type', 'hash', 'compile'
                    ]
                    if node.func.id in forbidden_calls:
                        raise ValueError(f"Security violation: Call to '{node.func.id}()' is forbidden")
    
    def load_script(self, script_name: str) -> Dict[str, Any]:
        """
        Load a script definition.
        
        Args:
            script_name: Name of the script (without extension)
            
        Returns:
            Script metadata and content
        """
        filepath = os.path.join(self.scripts_dir, f"{script_name}.json")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Script not found: {script_name}")
        
        with open(filepath, 'r') as f:
            script = json.load(f)
        
        return script
    
    def list_scripts(self) -> List[Dict[str, str]]:
        """
        List all available scripts.
        
        Returns:
            List of script metadata
        """
        if not os.path.exists(self.scripts_dir):
            return []
        
        scripts = []
        for filename in os.listdir(self.scripts_dir):
            if filename.endswith('.json'):
                try:
                    script = self.load_script(filename[:-5])
                    scripts.append({
                        "name": script.get("name", filename),
                        "description": script.get("description", "No description"),
                        "type": script.get("type", "unknown"),
                        "filename": filename,
                        "permissions": script.get("permissions", []),
                        "dependencies": script.get("dependencies", [])
                    })
                except:
                    pass
        
        return scripts
    
    async def execute_script(self, script_name: str) -> Dict[str, Any]:
        """
        Execute a script with security sandboxing.
        
        Args:
            script_name: Name of the script to execute
            
        Returns:
            Execution result with status and output
        """
        script = self.load_script(script_name)
        script_type = script.get("type", "python")
        script_content = script.get("script", "")
        permissions = script.get("permissions", [])
        dependencies = script.get("dependencies", [])
        
        # Validate permissions
        allowed_permissions = ["read_files", "write_files", "network_access", "system_access"]
        for perm in permissions:
            if perm not in allowed_permissions:
                return {"status": "error", "message": f"Invalid permission: {perm}"}
        
        # Check dependencies
        if dependencies:
            try:
                import subprocess
                result = subprocess.run(
                    ["pip", "install"] + dependencies,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    return {"status": "error", "message": f"Dependency installation failed: {result.stderr}"}
            except Exception as e:
                return {"status": "error", "message": f"Dependency check failed: {e}"}
        
        if script_type == "python":
            # Execute Python script in sandbox
            try:
                # Validate script content
                self._validate_python_script(script_content)

                # Define restricted builtins
                restricted_builtins = {
                    "print": print,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "list": list,
                    "dict": dict,
                    "set": set,
                    "tuple": tuple,
                    "range": range,
                    "enumerate": enumerate,
                    "zip": zip,
                    "map": map,
                    "filter": filter,
                    "sorted": sorted,
                    "sum": sum,
                    "max": max,
                    "min": min,
                    "abs": abs,
                    "round": round,
                    "pow": pow,
                    "divmod": divmod,
                    "isinstance": isinstance,
                    "issubclass": issubclass,
                    "callable": callable,
                    "Exception": Exception,
                    "ValueError": ValueError,
                    "TypeError": TypeError,
                    "RuntimeError": RuntimeError,
                    "StopIteration": StopIteration,
                    "ImportError": ImportError,
                    "IndexError": IndexError,
                    "KeyError": KeyError,
                }

                # Safe open implementation based on permissions
                def restricted_open(file, mode='r', *args, **kwargs):
                    if 'r' in mode and 'read_files' not in permissions and 'system_access' not in permissions:
                        raise PermissionError("Read access denied. 'read_files' permission required.")
                    if any(m in mode for m in 'wax+') and 'write_files' not in permissions and 'system_access' not in permissions:
                        raise PermissionError("Write access denied. 'write_files' permission required.")
                    return open(file, mode, *args, **kwargs)

                restricted_builtins["open"] = restricted_open

                # Restricted import implementation
                def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
                    if name in self.safe_modules:
                        return __import__(name, globals, locals, fromlist, level)

                    if name in ["os", "sys", "subprocess", "shutil", "pathlib", "threading", "asyncio", "logging"]:
                        if "system_access" in permissions:
                            return __import__(name, globals, locals, fromlist, level)
                        raise ImportError(f"Module '{name}' requires 'system_access' permission")

                    if "network_access" in permissions and name in ["socket", "http", "urllib", "requests"]:
                        return __import__(name, globals, locals, fromlist, level)

                    raise ImportError(f"Module '{name}' is not allowed in this sandbox")

                restricted_builtins["__import__"] = restricted_import

                # Create restricted execution environment
                exec_globals = {
                    "__builtins__": restricted_builtins,
                    "PERMISSIONS": permissions
                }
                
                # Pre-import allowed modules into globals for convenience
                for module in self.safe_modules:
                    try:
                        exec_globals[module] = __import__(module)
                    except:
                        pass
                
                if "system_access" in permissions:
                    for module in ["os", "sys", "subprocess", "shutil", "pathlib"]:
                        try:
                            exec_globals[module] = __import__(module)
                        except:
                            pass
                
                # Execute script
                exec(script_content, exec_globals)
                
                return {
                    "status": "success",
                    "message": "Script executed successfully",
                    "output": exec_globals.get("__result__", None)
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Script error: {e}",
                    "traceback": str(e)
                }
        
        elif script_type == "powershell":
            # Execute PowerShell script with security controls
            import subprocess
            try:
                # Basic PowerShell validation
                dangerous_ps_keywords = [
                    "Remove-Item", "Set-Content", "Get-Credential",
                    "Invoke-WebRequest", "Invoke-RestMethod", "Invoke-Expression",
                    "Start-Process", "Net-", "Add-Type", "Export-", "Import-Module"
                ]

                # Link validation to permissions
                for keyword in dangerous_ps_keywords:
                    if keyword.lower() in script_content.lower():
                        # If keyword is for network access, check that permission
                        if keyword in ["Invoke-WebRequest", "Invoke-RestMethod"] and "network_access" in permissions:
                            continue
                        # All other dangerous keywords require system_access
                        if "system_access" not in permissions:
                            return {"status": "error", "message": f"Security violation: PowerShell command '{keyword}' requires appropriate permissions"}

                # Create restricted execution policy with security flags
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", f"Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process; {script_content}"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                return {
                    "status": "success" if result.returncode == 0 else "error",
                    "output": result.stdout,
                    "error": result.stderr
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Script error: {e}"
                }
        
        else:
            return {"status": "error", "message": f"Unsupported script type: {script_type}"}

# Enhanced workflow management
class WorkflowManager:
    """
    Manages workflow lifecycle with advanced features.
    """
    
    def __init__(self, workflow_engine: WorkflowEngine):
        self.workflow_engine = workflow_engine
        self.workflow_history = []
        self.active_workflows = {}
    
    async def start_workflow(self, workflow_name: str, variables: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Start a workflow with tracking and monitoring.
        
        Args:
            workflow_name: Name of the workflow to start
            variables: Variable substitutions
            
        Returns:
            Workflow execution result
        """
        workflow_id = f"{workflow_name}_{int(time.time())}"
        
        # Start workflow execution
        execution_task = asyncio.create_task(
            self.workflow_engine.execute_workflow_with_monitoring(workflow_name, variables)
        )
        
        # Track active workflow
        self.active_workflows[workflow_id] = {
            "workflow_name": workflow_name,
            "variables": variables,
            "start_time": time.time(),
            "status": "running",
            "task": execution_task
        }
        
        try:
            # Wait for completion
            result = await execution_task
            
            # Update workflow history
            self.workflow_history.append({
                "id": workflow_id,
                "workflow_name": workflow_name,
                "variables": variables,
                "result": result,
                "completion_time": time.time()
            })
            
            return {
                "status": "success",
                "workflow_id": workflow_id,
                "result": result
            }
            
        except Exception as e:
            # Handle workflow failure
            self.workflow_history.append({
                "id": workflow_id,
                "workflow_name": workflow_name,
                "variables": variables,
                "error": str(e),
                "completion_time": time.time()
            })
            
            return {
                "status": "error",
                "workflow_id": workflow_id,
                "error": str(e)
            }
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get status of an active workflow."""
        if workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow["elapsed_time"] = time.time() - workflow["start_time"]
            return workflow
        return {"error": "Workflow not found"}
    
    def list_active_workflows(self) -> List[Dict[str, Any]]:
        """List all active workflows."""
        return list(self.active_workflows.values())
    
    def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get workflow execution history."""
        return self.workflow_history[-limit:]
    
    def cancel_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Cancel an active workflow."""
        if workflow_id in self.active_workflows:
            workflow = self.active_workflows[workflow_id]
            workflow["task"].cancel()
            del self.active_workflows[workflow_id]
            return {"status": "cancelled", "workflow_id": workflow_id}
        return {"error": "Workflow not found"}

# Global instances
workflow_engine = WorkflowEngine(graph)
workflow_manager = WorkflowManager(workflow_engine)

async def execute_workflow(workflow_name: str, variables: Dict[str, str] = None) -> Dict[str, Any]:
    """Main entry point for workflow execution."""
    return await workflow_manager.start_workflow(workflow_name, variables)

async def get_workflow_status(workflow_id: str) -> Dict[str, Any]:
    """Get status of a workflow."""
    return workflow_manager.get_workflow_status(workflow_id)

async def list_active_workflows() -> List[Dict[str, Any]]:
    """List all active workflows."""
    return workflow_manager.list_active_workflows()

async def get_workflow_history(limit: int = 10) -> List[Dict[str, Any]]:
    """Get workflow execution history."""
    return workflow_manager.get_workflow_history(limit)
