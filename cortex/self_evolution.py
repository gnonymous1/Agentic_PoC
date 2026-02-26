"""
Self-Evolution Engine
Enables the agent to safely modify its own code, create new tools, and evolve capabilities.
"""

import ast
import os
import shutil
import json
import time
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from cortex.events import EventBus, EventType


class CodeAnalysis:
    """Result of code analysis."""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.dependencies: List[str] = []
        self.complexity_score: float = 0.0
        self.modification_points: List[Dict[str, Any]] = []


class Modification:
    """Represents a code modification."""
    def __init__(self, mod_id: str, file_path: str, modification_type: str):
        self.id = mod_id
        self.file_path = file_path
        self.type = modification_type  # "add", "modify", "delete"
        self.original_content: Optional[str] = None
        self.new_content: Optional[str] = None
        self.backup_path: Optional[str] = None
        self.timestamp = datetime.now()
        self.applied = False
        self.validated = False


class ToolSpec:
    """Specification for creating a new tool."""
    def __init__(self, name: str, description: str, code: str):
        self.name = name
        self.description = description
        self.code = code
        self.parameters: Dict[str, Any] = {}
        self.return_type: str = "Any"


class SelfEvolutionEngine:
    """
    Engine for safe code modification and tool creation.
    """
    
    def __init__(self):
        self.event_bus = EventBus.get_sync()
        
        # Modification history
        self.modification_history: List[Modification] = []
        self.backup_dir = Path("backups/code_evolution")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Safety settings
        self.safe_mode = True
        self.require_approval = True
        
        # Protected files (cannot be modified)
        self.protected_files = [
            "cortex/events.py",
            "cortex/lifecycle.py",
            "server.py"
        ]
    
    def analyze_code(self, file_path: str) -> CodeAnalysis:
        """
        Analyze code structure and identify modification points.
        
        Args:
            file_path: Path to file to analyze
            
        Returns:
            CodeAnalysis object with detailed analysis
        """
        analysis = CodeAnalysis(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Parse AST
            tree = ast.parse(code)
            
            # Extract functions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis.functions.append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                        "decorators": [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                    })
                
                elif isinstance(node, ast.ClassDef):
                    methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    analysis.classes.append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "methods": methods,
                        "bases": [b.id if isinstance(b, ast.Name) else str(b) for b in node.bases]
                    })
                
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis.imports.append(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis.imports.append(node.module)
            
            # Calculate complexity (simplified)
            analysis.complexity_score = len(analysis.functions) * 0.5 + len(analysis.classes) * 1.0
            
            # Identify modification points
            analysis.modification_points = [
                {"type": "add_function", "location": "end_of_file"},
                {"type": "add_method", "classes": [c["name"] for c in analysis.classes]},
                {"type": "modify_function", "functions": [f["name"] for f in analysis.functions]}
            ]
            
            print(f"[EVOLUTION] Analyzed {file_path}: {len(analysis.functions)} functions, {len(analysis.classes)} classes")
            
            return analysis
            
        except Exception as e:
            print(f"[EVOLUTION] Error analyzing {file_path}: {e}")
            return analysis
    
    def propose_modification(self, file_path: str, intent: str, analysis: Optional[CodeAnalysis] = None) -> Modification:
        """
        Propose a code modification based on intent.
        
        Args:
            file_path: File to modify
            intent: Description of what to change
            analysis: Optional pre-computed analysis
            
        Returns:
            Modification object
        """
        # Check if file is protected
        if any(protected in file_path for protected in self.protected_files):
            raise ValueError(f"File {file_path} is protected and cannot be modified")
        
        # Generate modification ID
        mod_id = hashlib.md5(f"{file_path}{intent}{time.time()}".encode()).hexdigest()[:8]
        
        # Determine modification type
        if "add" in intent.lower() or "create" in intent.lower():
            mod_type = "add"
        elif "delete" in intent.lower() or "remove" in intent.lower():
            mod_type = "delete"
        else:
            mod_type = "modify"
        
        modification = Modification(mod_id, file_path, mod_type)
        
        # Read original content
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                modification.original_content = f.read()
        
        # Emit proposal event
        self.event_bus.emit_sync(
            EventType.SYSTEM_EVENT,
            {
                "action": "modification_proposed",
                "mod_id": mod_id,
                "file": file_path,
                "type": mod_type,
                "intent": intent
            },
            source="self_evolution"
        )
        
        print(f"[EVOLUTION] Proposed modification {mod_id}: {mod_type} to {file_path}")
        
        return modification
    
    def apply_modification(self, modification: Modification, safe_mode: bool = True) -> bool:
        """
        Apply a code modification with safety checks.
        
        Args:
            modification: Modification to apply
            safe_mode: If True, perform validation before applying
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create backup
            backup_path = self._create_backup(modification.file_path, modification.id)
            modification.backup_path = str(backup_path)
            
            # Validate if in safe mode
            if safe_mode:
                if not self._validate_modification(modification):
                    print(f"[EVOLUTION] Modification {modification.id} failed validation")
                    return False
                modification.validated = True
            
            # Apply modification
            if modification.new_content:
                with open(modification.file_path, 'w', encoding='utf-8') as f:
                    f.write(modification.new_content)
                
                modification.applied = True
                self.modification_history.append(modification)
                
                # Emit success event
                self.event_bus.emit_sync(
                    EventType.SYSTEM_EVENT,
                    {
                        "action": "modification_applied",
                        "mod_id": modification.id,
                        "file": modification.file_path,
                        "validated": modification.validated
                    },
                    source="self_evolution"
                )
                
                print(f"[EVOLUTION] Applied modification {modification.id} to {modification.file_path}")
                return True
            else:
                print(f"[EVOLUTION] No new content to apply for {modification.id}")
                return False
                
        except Exception as e:
            print(f"[EVOLUTION] Error applying modification {modification.id}: {e}")
            
            # Emit error event
            self.event_bus.emit_sync(
                EventType.SYSTEM_ERROR,
                {
                    "action": "modification_failed",
                    "mod_id": modification.id,
                    "error": str(e)
                },
                source="self_evolution"
            )
            
            return False
    
    def create_tool(self, spec: ToolSpec) -> Optional[Any]:
        """
        Create a new tool from specification.
        
        Args:
            spec: Tool specification
            
        Returns:
            Created tool function or None if failed
        """
        try:
            # Validate tool spec
            if not self._validate_tool_spec(spec):
                print(f"[EVOLUTION] Invalid tool spec for {spec.name}")
                return None
            
            # Create tool file
            tool_dir = Path("agent_fabric/custom_tools")
            tool_dir.mkdir(parents=True, exist_ok=True)
            
            tool_file = tool_dir / f"{spec.name}.py"
            
            # Generate tool code
            tool_code = f'''"""
{spec.description}
Auto-generated tool by Self-Evolution Engine
"""

{spec.code}

# Tool metadata
TOOL_NAME = "{spec.name}"
TOOL_DESCRIPTION = "{spec.description}"
'''
            
            # Write tool file
            with open(tool_file, 'w', encoding='utf-8') as f:
                f.write(tool_code)
            
            # Validate syntax
            try:
                with open(tool_file, 'r', encoding='utf-8') as f:
                    ast.parse(f.read())
            except SyntaxError as e:
                print(f"[EVOLUTION] Syntax error in generated tool: {e}")
                tool_file.unlink()  # Delete invalid file
                return None
            
            # Emit tool creation event
            self.event_bus.emit_sync(
                EventType.SYSTEM_EVENT,
                {
                    "action": "tool_created",
                    "tool_name": spec.name,
                    "file": str(tool_file)
                },
                source="self_evolution"
            )
            
            print(f"[EVOLUTION] Created tool: {spec.name} at {tool_file}")
            
            # Import and return tool
            import importlib.util
            spec_import = importlib.util.spec_from_file_location(spec.name, tool_file)
            if spec_import and spec_import.loader:
                module = importlib.util.module_from_spec(spec_import)
                spec_import.loader.exec_module(module)
                
                # Find the main function (assume it's the tool name or first function)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if callable(attr) and not attr_name.startswith('_'):
                        return attr
            
            return None
            
        except Exception as e:
            print(f"[EVOLUTION] Error creating tool {spec.name}: {e}")
            return None
    
    def rollback(self, modification_id: str) -> bool:
        """
        Rollback a modification to previous state.
        
        Args:
            modification_id: ID of modification to rollback
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Find modification
            modification = None
            for mod in self.modification_history:
                if mod.id == modification_id:
                    modification = mod
                    break
            
            if not modification:
                print(f"[EVOLUTION] Modification {modification_id} not found")
                return False
            
            if not modification.backup_path or not os.path.exists(modification.backup_path):
                print(f"[EVOLUTION] Backup not found for {modification_id}")
                return False
            
            # Restore from backup
            shutil.copy2(modification.backup_path, modification.file_path)
            
            # Mark as rolled back
            modification.applied = False
            
            # Emit rollback event
            self.event_bus.emit_sync(
                EventType.SYSTEM_EVENT,
                {
                    "action": "modification_rolled_back",
                    "mod_id": modification_id,
                    "file": modification.file_path
                },
                source="self_evolution"
            )
            
            print(f"[EVOLUTION] Rolled back modification {modification_id}")
            return True
            
        except Exception as e:
            print(f"[EVOLUTION] Error rolling back {modification_id}: {e}")
            return False
    
    def get_modification_history(self) -> List[Dict[str, Any]]:
        """Get modification history."""
        return [
            {
                "id": mod.id,
                "file": mod.file_path,
                "type": mod.type,
                "timestamp": mod.timestamp.isoformat(),
                "applied": mod.applied,
                "validated": mod.validated
            }
            for mod in self.modification_history
        ]
    
    def _create_backup(self, file_path: str, mod_id: str) -> Path:
        """Create backup of file before modification."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{Path(file_path).stem}_{mod_id}_{timestamp}{Path(file_path).suffix}"
        backup_path = self.backup_dir / backup_name
        
        if os.path.exists(file_path):
            shutil.copy2(file_path, backup_path)
            print(f"[EVOLUTION] Created backup: {backup_path}")
        
        return backup_path
    
    def _validate_modification(self, modification: Modification) -> bool:
        """Validate modification before applying."""
        if not modification.new_content:
            return False
        
        # Check syntax
        try:
            ast.parse(modification.new_content)
        except SyntaxError as e:
            print(f"[EVOLUTION] Syntax error in modification: {e}")
            return False
        
        # Check imports are valid
        try:
            tree = ast.parse(modification.new_content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    # Basic import validation (could be enhanced)
                    pass
        except Exception as e:
            print(f"[EVOLUTION] Import validation failed: {e}")
            return False
        
        return True
    
    def _validate_tool_spec(self, spec: ToolSpec) -> bool:
        """Validate tool specification."""
        if not spec.name or not spec.code:
            return False
        
        # Check for valid Python identifier
        if not spec.name.isidentifier():
            return False
        
        # Validate code syntax
        try:
            ast.parse(spec.code)
        except SyntaxError:
            return False
        
        return True


# Global instance
evolution_engine = SelfEvolutionEngine()


def analyze_code(file_path: str) -> CodeAnalysis:
    """Analyze code structure."""
    return evolution_engine.analyze_code(file_path)


def propose_modification(file_path: str, intent: str) -> Modification:
    """Propose a code modification."""
    return evolution_engine.propose_modification(file_path, intent)


def apply_modification(modification: Modification, safe_mode: bool = True) -> bool:
    """Apply a modification."""
    return evolution_engine.apply_modification(modification, safe_mode)


def create_tool(spec: ToolSpec) -> Optional[Any]:
    """Create a new tool."""
    return evolution_engine.create_tool(spec)


def rollback_modification(modification_id: str) -> bool:
    """Rollback a modification."""
    return evolution_engine.rollback(modification_id)


def get_modification_history() -> List[Dict[str, Any]]:
    """Get modification history."""
    return evolution_engine.get_modification_history()
