"""
Synthesis Thinking Model
Autonomous task decomposition, planning, and execution orchestration with advanced risk assessment and self-reflection.
"""

from typing import List, Dict, Any, Optional, Tuple
from cortex.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
import json
import asyncio
import time
from cortex.state import AgentState
# WorkflowEngine imported lazily to avoid circular dependency


class RiskAssessment:
    """Advanced risk assessment module for task planning."""
    
    def __init__(self):
        self.risk_categories = {
            "security": {"weight": 0.3, "description": "Security and privacy risks"},
            "reliability": {"weight": 0.25, "description": "Reliability and stability risks"},
            "performance": {"weight": 0.2, "description": "Performance and resource risks"},
            "compliance": {"weight": 0.15, "description": "Compliance and policy risks"},
            "complexity": {"weight": 0.1, "description": "Complexity and maintainability risks"}
        }
    
    def assess_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risks for a specific task.
        
        Args:
            task: Task definition to assess
            
        Returns:
            Risk assessment results
        """
        risk_factors = {
            "security": self._assess_security(task),
            "reliability": self._assess_reliability(task),
            "performance": self._assess_performance(task),
            "compliance": self._assess_compliance(task),
            "complexity": self._assess_complexity(task)
        }
        
        # Calculate overall risk score
        overall_score = sum(
            risk_factors[category]["score"] * self.risk_categories[category]["weight"]
            for category in risk_factors
        )
        
        return {
            "overall_score": overall_score,
            "risk_factors": risk_factors,
            "severity": self._determine_severity(overall_score),
            "mitigations": self._suggest_mitigations(task, risk_factors),
            "confidence": self._calculate_confidence(task)
        }
    
    def _assess_security(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Assess security risks for a task."""
        security_risks = []
        
        # Check for security-sensitive operations
        security_sensitive_actions = ["system_shell_exec", "system_file_operations", "network_access"]
        if any(action in task.get("action", "") for action in security_sensitive_actions):
            security_risks.append("Security-sensitive operation detected")
        
        # Check for data access patterns
        if task.get("params", {}).get("access_data"):
            security_risks.append("Data access operation detected")
        
        # Calculate risk score
        risk_score = min(1.0, len(security_risks) * 0.3)
        
        return {
            "score": risk_score,
            "risks": security_risks,
            "severity": "high" if risk_score > 0.5 else "medium" if risk_score > 0.2 else "low"
        }
    
    def _assess_reliability(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Assess reliability risks for a task."""
        reliability_risks = []
        
        # Check for external dependencies
        if task.get("params", {}).get("external_service"):
            reliability_risks.append("External service dependency")
        
        # Check for error handling
        if not task.get("params", {}).get("error_handling"):
            reliability_risks.append("No error handling specified")
        
        # Calculate risk score
        risk_score = min(1.0, len(reliability_risks) * 0.4)
        
        return {
            "score": risk_score,
            "risks": reliability_risks,
            "severity": "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low"
        }
    
    def _assess_performance(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Assess performance risks for a task."""
        performance_risks = []
        
        # Check for resource-intensive operations
        resource_intensive_actions = ["process_large_data", "complex_computation", "multiple_apis"]
        if any(action in task.get("action", "") for action in resource_intensive_actions):
            performance_risks.append("Resource-intensive operation")
        
        # Check for data volume
        if task.get("params", {}).get("data_size") and task["params"]["data_size"] > 1000000:
            performance_risks.append("Large data volume detected")
        
        # Calculate risk score
        risk_score = min(1.0, len(performance_risks) * 0.5)
        
        return {
            "score": risk_score,
            "risks": performance_risks,
            "severity": "high" if risk_score > 0.7 else "medium" if risk_score > 0.4 else "low"
        }
    
    def _assess_compliance(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Assess compliance risks for a task."""
        compliance_risks = []
        
        # Check for data privacy concerns
        if task.get("params", {}).get("personal_data"):
            compliance_risks.append("Personal data handling")
        
        # Check for regulatory requirements
        if task.get("params", {}).get("regulatory_requirement"):
            compliance_risks.append("Regulatory requirement detected")
        
        # Calculate risk score
        risk_score = min(1.0, len(compliance_risks) * 0.6)
        
        return {
            "score": risk_score,
            "risks": compliance_risks,
            "severity": "high" if risk_score > 0.5 else "medium" if risk_score > 0.2 else "low"
        }
    
    def _assess_complexity(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Assess complexity risks for a task."""
        complexity_risks = []
        
        # Check for complex dependencies
        if task.get("depends_on") and len(task["depends_on"]) > 3:
            complexity_risks.append("Complex dependency chain")
        
        # Check for multiple technologies
        if len(set(task.get("params", {}).get("technologies", []))) > 2:
            complexity_risks.append("Multiple technology stack")
        
        # Calculate risk score
        risk_score = min(1.0, len(complexity_risks) * 0.4)
        
        return {
            "score": risk_score,
            "risks": complexity_risks,
            "severity": "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low"
        }
    
    def _determine_severity(self, score: float) -> str:
        """Determine severity level based on risk score."""
        if score > 0.7:
            return "critical"
        elif score > 0.4:
            return "high"
        elif score > 0.2:
            return "medium"
        else:
            return "low"
    
    def _suggest_mitigations(self, task: Dict[str, Any], risk_factors: Dict[str, Any]) -> List[str]:
        """Suggest risk mitigations based on assessment."""
        mitigations = []
        
        # Security mitigations
        if risk_factors["security"]["score"] > 0.3:
            mitigations.append("Implement proper authentication and authorization")
            mitigations.append("Use encryption for sensitive data")
        
        # Reliability mitigations
        if risk_factors["reliability"]["score"] > 0.3:
            mitigations.append("Implement retry logic with exponential backoff")
            mitigations.append("Add comprehensive error handling")
        
        # Performance mitigations
        if risk_factors["performance"]["score"] > 0.3:
            mitigations.append("Implement caching for frequently accessed data")
            mitigations.append("Use asynchronous processing for long-running tasks")
        
        # Compliance mitigations
        if risk_factors["compliance"]["score"] > 0.2:
            mitigations.append("Implement data anonymization for personal data")
            mitigations.append("Add audit logging for compliance tracking")
        
        # Complexity mitigations
        if risk_factors["complexity"]["score"] > 0.3:
            mitigations.append("Break down complex tasks into smaller, manageable units")
            mitigations.append("Implement comprehensive documentation")
        
        return mitigations
    
    def _calculate_confidence(self, task: Dict[str, Any]) -> float:
        """Calculate confidence level based on task characteristics."""
        confidence_factors = []
        
        # Check for clear requirements
        if task.get("description") and len(task["description"]) > 20:
            confidence_factors.append(0.2)
        
        # Check for available tools
        if task.get("tool") and task.get("agent"):
            confidence_factors.append(0.3)
        
        # Check for defined parameters
        if task.get("params") and len(task["params"]) > 0:
            confidence_factors.append(0.2)
        
        # Check for dependencies
        if not task.get("depends_on") or len(task["depends_on"]) < 3:
            confidence_factors.append(0.2)
        
        return sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5


class SelfReflection:
    """Advanced self-reflection module for continuous improvement."""
    
    def __init__(self):
        self.reflection_history = []
        self.learning_rate = 0.1
    
    def reflect_on_execution(self, plan: Dict[str, Any], execution_log: List[str], actual_results: Any) -> Dict[str, Any]:
        """
        Analyze execution results and generate insights for improvement.
        
        Args:
            plan: Original execution plan
            execution_log: Log of what actually happened
            actual_results: Actual results obtained
            
        Returns:
            Reflection analysis with improvement suggestions
        """
        reflection = {
            "analysis": {},
            "insights": [],
            "improvements": [],
            "learning_points": [],
            "confidence_adjustment": 0.0
        }
        
        # Analyze plan vs execution
        reflection["analysis"]["plan_completeness"] = self._assess_plan_completeness(plan, execution_log)
        reflection["analysis"]["execution_accuracy"] = self._assess_execution_accuracy(plan, execution_log)
        reflection["analysis"]["risk_identification"] = self._assess_risk_identification(plan, execution_log)
        reflection["analysis"]["resource_utilization"] = self._assess_resource_utilization(execution_log)
        
        # Generate insights
        reflection["insights"] = self._generate_insights(plan, execution_log, actual_results)
        
        # Suggest improvements
        reflection["improvements"] = self._suggest_improvements(plan, execution_log, actual_results)
        
        # Identify learning points
        reflection["learning_points"] = self._identify_learning_points(plan, execution_log, actual_results)
        
        # Calculate confidence adjustment
        reflection["confidence_adjustment"] = self._calculate_confidence_adjustment(reflection)
        
        # Store reflection
        self.reflection_history.append({
            "timestamp": time.time(),
            "plan_id": plan.get("task_analysis", "unknown"),
            "reflection": reflection
        })
        
        return reflection
    
    def _assess_plan_completeness(self, plan: Dict[str, Any], execution_log: List[str]) -> Dict[str, Any]:
        """Assess how complete the original plan was."""
        completeness = {
            "subtasks_covered": 0,
            "dependencies_identified": 0,
            "risks_identified": 0,
            "resources_specified": 0,
            "overall_score": 0.0
        }
        
        # Assess subtask coverage
        if plan.get("subtasks"):
            completeness["subtasks_covered"] = min(1.0, len(plan["subtasks"]) * 0.2)
        
        # Assess dependency identification
        if plan.get("subtasks"):
            identified_deps = sum(1 for task in plan["subtasks"] if task.get("depends_on"))
            completeness["dependencies_identified"] = min(1.0, identified_deps * 0.3)
        
        # Assess risk identification
        if plan.get("risk_assessment"):
            completeness["risks_identified"] = 0.5  # Risk assessment was attempted
        
        # Calculate overall score
        completeness["overall_score"] = sum(completeness.values()) / len(completeness)
        
        return completeness
    
    def _assess_execution_accuracy(self, plan: Dict[str, Any], execution_log: List[str]) -> Dict[str, Any]:
        """Assess how accurately the plan was executed."""
        accuracy = {
            "steps_executed": 0,
            "deviations_occurred": 0,
            "errors_encountered": 0,
            "corrections_needed": 0,
            "overall_score": 0.0
        }
        
        # Count executed steps
        executed_steps = sum(1 for log in execution_log if "Completed" in log or "executed" in log.lower())
        total_steps = len([log for log in execution_log if "Step" in log])
        accuracy["steps_executed"] = executed_steps / total_steps if total_steps > 0 else 0
        
        # Count deviations
        deviations = sum(1 for log in execution_log if "deviated" in log.lower() or "changed" in log.lower())
        accuracy["deviations_occurred"] = min(1.0, deviations * 0.2)
        
        # Count errors
        errors = sum(1 for log in execution_log if "Error" in log or "failed" in log.lower())
        accuracy["errors_encountered"] = min(1.0, errors * 0.3)
        
        # Calculate overall score
        accuracy["overall_score"] = sum(accuracy.values()) / len(accuracy)
        
        return accuracy
    
    def _assess_risk_identification(self, plan: Dict[str, Any], execution_log: List[str]) -> Dict[str, Any]:
        """Assess how well risks were identified and managed."""
        risk_assessment = {
            "predicted_risks": 0,
            "actual_risks_encountered": 0,
            "predicted_vs_actual_match": 0.0,
            "risk_mitigations_applied": 0,
            "overall_score": 0.0
        }
        
        # Count predicted risks
        if plan.get("risk_assessment"):
            predicted_risks = plan["risk_assessment"].get("risk_factors", {})
            risk_assessment["predicted_risks"] = len(predicted_risks)
        
        # Count actual risks encountered
        actual_risks = sum(1 for log in execution_log if "risk" in log.lower() or "issue" in log.lower())
        risk_assessment["actual_risks_encountered"] = actual_risks
        
        # Calculate prediction accuracy
        if risk_assessment["predicted_risks"] > 0:
            risk_assessment["predicted_vs_actual_match"] = min(1.0, actual_risks / risk_assessment["predicted_risks"])
        
        # Count applied mitigations
        mitigations = sum(1 for log in execution_log if "mitigation" in log.lower() or "fix" in log.lower())
        risk_assessment["risk_mitigations_applied"] = mitigations
        
        # Calculate overall score
        risk_assessment["overall_score"] = sum(risk_assessment.values()) / len(risk_assessment)
        
        return risk_assessment
    
    def _assess_resource_utilization(self, execution_log: List[str]) -> Dict[str, Any]:
        """Assess resource utilization during execution."""
        utilization = {
            "memory_usage": 0.0,
            "cpu_usage": 0.0,
            "execution_time": 0.0,
            "resource_efficiency": 0.0
        }
        
        # Estimate resource usage from logs (simplified)
        time_logs = [log for log in execution_log if "time" in log.lower() or "duration" in log.lower()]
        if time_logs:
            utilization["execution_time"] = len(time_logs) * 0.1  # Simplified estimation
        
        # Resource efficiency based on errors
        errors = sum(1 for log in execution_log if "Error" in log)
        total_steps = len([log for log in execution_log if "Step" in log])
        if total_steps > 0:
            utilization["resource_efficiency"] = 1.0 - (errors / total_steps)
        
        return utilization
    
    def _generate_insights(self, plan: Dict[str, Any], execution_log: List[str], actual_results: Any) -> List[str]:
        """Generate insights from execution analysis."""
        insights = []
        
        # Insight: Plan vs Reality
        if len(execution_log) > len(plan.get("subtasks", [])):
            insights.append("Execution involved more steps than originally planned")
        
        # Insight: Risk Management
        if "risk_assessment" in plan:
            insights.append(f"Risk assessment identified {len(plan['risk_assessment'].get('risk_factors', {}))} potential risks")
        
        # Insight: Performance
        if actual_results and hasattr(actual_results, "__len__"):
            insights.append(f"Task produced {len(actual_results)} results")
        
        return insights
    
    def _suggest_improvements(self, plan: Dict[str, Any], execution_log: List[str], actual_results: Any) -> List[str]:
        """Suggest improvements based on execution analysis."""
        improvements = []
        
        # Improvement: Error Handling
        if any("Error" in log for log in execution_log):
            improvements.append("Enhance error handling mechanisms")
        
        # Improvement: Planning
        if len(execution_log) > len(plan.get("subtasks", [])) * 1.5:
            improvements.append("Improve task decomposition granularity")
        
        # Improvement: Risk Management
        if "risk_assessment" in plan:
            improvements.append("Refine risk assessment criteria based on actual outcomes")
        
        return improvements
    
    def _identify_learning_points(self, plan: Dict[str, Any], execution_log: List[str], actual_results: Any) -> List[str]:
        """Identify learning points from execution."""
        learning_points = []
        
        # Learning: Process
        learning_points.append("Documented execution process for future reference")
        
        # Learning: Tools
        if actual_results and hasattr(actual_results, "__dict__"):
            learning_points.append(f"Learned about tool capabilities: {list(actual_results.__dict__.keys())}")
        
        return learning_points
    
    def _calculate_confidence_adjustment(self, reflection: Dict[str, Any]) -> float:
        """Calculate confidence adjustment based on reflection analysis."""
        adjustment_factors = []
        
        # Adjust based on plan completeness
        if reflection["analysis"]["plan_completeness"]["overall_score"] > 0.7:
            adjustment_factors.append(0.1)
        elif reflection["analysis"]["plan_completeness"]["overall_score"] < 0.3:
            adjustment_factors.append(-0.1)
        
        # Adjust based on execution accuracy
        if reflection["analysis"]["execution_accuracy"]["overall_score"] > 0.8:
            adjustment_factors.append(0.2)
        elif reflection["analysis"]["execution_accuracy"]["overall_score"] < 0.4:
            adjustment_factors.append(-0.2)
        
        return sum(adjustment_factors) / len(adjustment_factors) if adjustment_factors else 0.0


class SynthesisThinkingModel:
    """
    Advanced reasoning model with risk assessment and self-reflection capabilities.
    """
    
    def __init__(self):
        self.llm = get_llm(role="reasoner")
        self.risk_assessor = RiskAssessment()
        self.self_reflection = SelfReflection()
        # Lazy import to avoid circular dependency
        self._workflow_engine = None
        
        self.planning_prompt = """You are a Synthesis Thinking Model for AgentOS with advanced capabilities.
Your role is to decompose complex user requests into structured, executable workflows with comprehensive risk assessment.

ENHANCED CAPABILITIES:
- Break down tasks into atomic subtasks with dependency analysis
- Identify required agents and tools with capability matching
- Sequence operations with advanced dependency management
- Perform comprehensive risk assessment for each task
- Generate executable workflow definitions with risk mitigation
- Self-reflect on execution outcomes for continuous improvement

OUTPUT FORMAT (JSON):
{
    "task_analysis": "Brief analysis of the request",
    "subtasks": [
        {
            "id": 1,
            "description": "What to do",
            "agent": "Which agent (Operator, Surfer, Researcher, etc.)",
            "tool": "Specific tool to use",
            "params": {"param1": "value1"},
            "depends_on": []  // List of subtask IDs this depends on
        }
    ],
    "risk_assessment": {
        "overall_score": 0.0,
        "risk_factors": {
            "security": {"score": 0.0, "risks": [], "severity": "low"},
            "reliability": {"score": 0.0, "risks": [], "severity": "low"},
            "performance": {"score": 0.0, "risks": [], "severity": "low"},
            "compliance": {"score": 0.0, "risks": [], "severity": "low"},
            "complexity": {"score": 0.0, "risks": [], "severity": "low"}
        },
        "severity": "low",
        "mitigations": [],
        "confidence": 0.5
    },
    "estimated_duration": "Time estimate",
    "self_reflection": {
        "analysis": {},
        "insights": [],
        "improvements": [],
        "learning_points": [],
        "confidence_adjustment": 0.0
    }
}

THINK STEP-BY-STEP. BE THOROUGH AND ANALYTICAL."""
    
    @property
    def workflow_engine(self):
        """Lazy load WorkflowEngine to avoid circular import"""
        if self._workflow_engine is None:
            from cortex.workflow_engine import WorkflowEngine
            from cortex.graph import graph
            self._workflow_engine = WorkflowEngine(graph)
        return self._workflow_engine

    
    def decompose_task(self, user_request: str) -> Dict[str, Any]:
        """
        Decompose a complex user request into structured subtasks with risk assessment.
        
        Args:
            user_request: The user's natural language request
            
        Returns:
            Structured workflow plan with risk assessment and self-reflection
        """
        messages = [
            SystemMessage(content=self.planning_prompt),
            HumanMessage(content=f"USER REQUEST: {user_request}\n\nGenerate a detailed execution plan with comprehensive risk assessment.")
        ]
        
        response = self.llm.invoke(messages)
        
        try:
            # Extract JSON from response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            plan = json.loads(content.strip())
            
            # Perform risk assessment
            if plan.get("subtasks"):
                plan["risk_assessment"] = self._perform_comprehensive_risk_assessment(plan)
            
            return plan
            
        except Exception as e:
            print(f"[SYNTHESIS] Error parsing plan: {e}")
            return {
                "task_analysis": "Failed to parse plan",
                "subtasks": [],
                "risk_assessment": {
                    "overall_score": 1.0,
                    "risk_factors": {"complexity": {"score": 1.0, "severity": "critical"}},
                    "severity": "critical",
                    "mitigations": ["Review and simplify task request"],
                    "confidence": 0.1
                },
                "estimated_duration": "unknown",
                "self_reflection": {
                    "analysis": {"plan_completeness": {"overall_score": 0.0}},
                    "insights": ["Task decomposition failed"],
                    "improvements": ["Improve error handling in synthesis"],
                    "learning_points": ["Handle parsing errors gracefully"],
                    "confidence_adjustment": -0.5
                }
            }
    
    def _perform_comprehensive_risk_assessment(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive risk assessment for all subtasks."""
        risk_assessor = RiskAssessment()
        
        if not plan.get("subtasks"):
            return {
                "overall_score": 0.0,
                "risk_factors": {},
                "severity": "low",
                "mitigations": [],
                "confidence": 0.5
            }
        
        # Assess each subtask
        subtask_risks = []
        for subtask in plan["subtasks"]:
            task_risk = risk_assessor.assess_task(subtask)
            subtask_risks.append(task_risk)
        
        # Calculate overall risk
        overall_score = sum(risk["overall_score"] for risk in subtask_risks) / len(subtask_risks)
        
        # Aggregate risk factors
        aggregated_risks = {}
        for category in risk_assessor.risk_categories:
            scores = [risk["risk_factors"].get(category, {"score": 0.0})["score"] for risk in subtask_risks]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            
            aggregated_risks[category] = {
                "score": avg_score,
                "severity": self._determine_severity(avg_score),
                "risks": [risk for risk in sum([risk["risk_factors"].get(category, {"risks": []})["risks"] for risk in subtask_risks], [])]
            }
        
        # Generate overall mitigations
        all_mitigations = set()
        for risk in subtask_risks:
            all_mitigations.update(risk["mitigations"])
        
        # Calculate confidence
        confidence_scores = [risk["confidence"] for risk in subtask_risks]
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        
        return {
            "overall_score": overall_score,
            "risk_factors": aggregated_risks,
            "severity": self._determine_severity(overall_score),
            "mitigations": list(all_mitigations),
            "confidence": overall_confidence
        }
    
    def reflect_on_execution(self, plan: Dict[str, Any], execution_log: List[str], actual_results: Any) -> Dict[str, Any]:
        """
        Analyze execution results and generate comprehensive reflection.
        
        Args:
            plan: Original execution plan
            execution_log: Log of what actually happened
            actual_results: Actual results obtained
            
        Returns:
            Reflection analysis with improvement suggestions
        """
        reflection = self.self_reflection.reflect_on_execution(plan, execution_log, actual_results)
        
        # Add plan-specific analysis
        reflection["analysis"]["plan_vs_execution_comparison"] = self._compare_plan_vs_execution(plan, execution_log)
        reflection["analysis"]["risk_management_effectiveness"] = self._assess_risk_management(plan, execution_log)
        
        return reflection
    
    def _compare_plan_vs_execution(self, plan: Dict[str, Any], execution_log: List[str]) -> Dict[str, Any]:
        """Compare planned vs actual execution."""
        comparison = {
            "planned_steps": len(plan.get("subtasks", [])),
            "executed_steps": len([log for log in execution_log if "Step" in log]),
            "deviations": 0,
            "unplanned_steps": 0,
            "accuracy_score": 0.0
        }
        
        # Count deviations and unplanned steps
        for log in execution_log:
            if "deviated" in log.lower() or "changed" in log.lower():
                comparison["deviations"] += 1
            if "unplanned" in log.lower() or "additional" in log.lower():
                comparison["unplanned_steps"] += 1
        
        # Calculate accuracy score
        if comparison["planned_steps"] > 0:
            comparison["accuracy_score"] = 1.0 - (comparison["deviations"] / comparison["planned_steps"])
        
        return comparison
    
    def _assess_risk_management(self, plan: Dict[str, Any], execution_log: List[str]) -> Dict[str, Any]:
        """Assess effectiveness of risk management."""
        risk_management = {
            "predicted_risks": 0,
            "actual_risks_encountered": 0,
            "mitigated_risks": 0,
            "unmitigated_risks": 0,
            "effectiveness_score": 0.0
        }
        
        # Count predicted risks
        if plan.get("risk_assessment"):
            risk_management["predicted_risks"] = len(plan["risk_assessment"].get("risk_factors", {}))
        
        # Count actual risks
        actual_risks = sum(1 for log in execution_log if "risk" in log.lower() or "issue" in log.lower())
        risk_management["actual_risks_encountered"] = actual_risks
        
        # Count mitigated risks
        mitigated = sum(1 for log in execution_log if "mitigation" in log.lower() or "resolved" in log.lower())
        risk_management["mitigated_risks"] = mitigated
        
        # Calculate unmitigated risks
        risk_management["unmitigated_risks"] = max(0, actual_risks - mitigated)
        
        # Calculate effectiveness score
        if risk_management["predicted_risks"] > 0:
            risk_management["effectiveness_score"] = mitigated / risk_management["predicted_risks"]
        
        return risk_management
    
    def generate_workflow_yaml(self, plan: Dict[str, Any]) -> str:
        """
        Convert a structured plan into YAML workflow format with risk information.
        
        Args:
            plan: Structured execution plan
            
        Returns:
            YAML workflow definition
        """
        workflow_name = plan.get("task_analysis", "Generated Workflow")[:50]
        subtasks = plan.get("subtasks", [])
        
        yaml_lines = [
            f"name: '{workflow_name}'",
            f"description: '{plan.get('task_analysis', 'Auto-generated workflow')}'",
            "steps:"
        ]
        
        for task in subtasks:
            yaml_lines.append(f"  - agent: '{task.get('agent', 'Operator')}'")
            yaml_lines.append(f"    action: '{task.get('tool', 'unknown')}'")
            
            if task.get("params"):
                yaml_lines.append("    params:")
                for key, value in task["params"].items():
                    yaml_lines.append(f"      {key}: '{value}'")
            
            if task.get("depends_on"):
                yaml_lines.append(f"    depends_on: {task['depends_on']}")
            
            yaml_lines.append("")
        
        # Add risk information
        if plan.get("risk_assessment"):
            yaml_lines.append("risk_assessment:")
            yaml_lines.append(f"  overall_score: {plan['risk_assessment']['overall_score']}")
            yaml_lines.append("  risk_factors:")
            for category, factors in plan["risk_assessment"]["risk_factors"].items():
                yaml_lines.append(f"    {category}:")
                yaml_lines.append(f"      score: {factors['score']}")
                yaml_lines.append(f"      severity: {factors['severity']}")
            yaml_lines.append(f"  severity: {plan['risk_assessment']['severity']}")
            yaml_lines.append(f"  confidence: {plan['risk_assessment']['confidence']}")
        
        return '\n'.join(yaml_lines)
    
    def _determine_severity(self, score: float) -> str:
        """Determine severity level based on risk score."""
        if score > 0.7:
            return "critical"
        elif score > 0.4:
            return "high"
        elif score > 0.2:
            return "medium"
        else:
            return "low"


import time
import asyncio
from typing import Optional, List, Dict, Any

class ExecutionOrchestrator:
    """
    Orchestrates plan execution with progress tracking, failure handling, and EventBus integration.
    """
    
    def __init__(self):
        from cortex.events import EventBus, EventType
        self.event_bus = EventBus.get_sync()
        self.EventType = EventType
        
        # Active plans: plan_id -> plan data
        self.active_plans: Dict[str, Dict[str, Any]] = {}
        
        # Execution state
        self.execution_logs: Dict[str, List[str]] = {}
        self.execution_results: Dict[str, Any] = {}
    
    async def execute_plan(self, plan: Dict[str, Any], plan_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a synthesis plan with progress tracking and event emission.
        
        Args:
            plan: Structured execution plan
            plan_id: Optional plan identifier
            
        Returns:
            Execution result with status and outputs
        """
        import uuid
        
        if plan_id is None:
            plan_id = str(uuid.uuid4())
        
        # Initialize execution state
        self.active_plans[plan_id] = {
            "plan": plan,
            "status": "initializing",
            "current_task": None,
            "completed_tasks": [],
            "failed_tasks": [],
            "start_time": time.time()
        }
        
        self.execution_logs[plan_id] = []
        
        # Emit plan started event
        self.event_bus.emit_sync(
            self.EventType.WORKFLOW_STARTED,
            {
                "plan_id": plan_id,
                "task_analysis": plan.get("task_analysis", ""),
                "total_tasks": len(plan.get("subtasks", []))
            },
            source="synthesis_orchestrator"
        )
        
        try:
            # Update status to running
            self.active_plans[plan_id]["status"] = "running"
            
            # Execute subtasks
            subtasks = plan.get("subtasks", [])
            results = []
            
            for idx, task in enumerate(subtasks):
                # Check dependencies
                if not await self._check_dependencies(plan_id, task):
                    self._log(plan_id, f"Task {task.get('id', idx)} waiting for dependencies")
                    continue
                
                # Update current task
                self.active_plans[plan_id]["current_task"] = task
                
                # Emit task started event
                self.event_bus.emit_sync(
                    self.EventType.AGENT_STATE_CHANGE,
                    {
                        "plan_id": plan_id,
                        "task_id": task.get("id", idx),
                        "action": "task_started",
                        "description": task.get("description", "")
                    },
                    source="synthesis_orchestrator"
                )
                
                self._log(plan_id, f"Executing task {task.get('id', idx)}: {task.get('description', '')}")
                
                # Execute task
                try:
                    result = await self._execute_task(plan_id, task)
                    results.append(result)
                    
                    # Mark as completed
                    self.active_plans[plan_id]["completed_tasks"].append(task.get("id", idx))
                    
                    # Emit task completed event
                    self.event_bus.emit_sync(
                        self.EventType.AGENT_COMPLETED,
                        {
                            "plan_id": plan_id,
                            "task_id": task.get("id", idx),
                            "result_preview": str(result)[:100]
                        },
                        source="synthesis_orchestrator"
                    )
                    
                    self._log(plan_id, f"Task {task.get('id', idx)} completed successfully")
                    
                except Exception as e:
                    # Handle task failure
                    self.active_plans[plan_id]["failed_tasks"].append(task.get("id", idx))
                    
                    # Emit task error event
                    self.event_bus.emit_sync(
                        self.EventType.AGENT_ERROR,
                        {
                            "plan_id": plan_id,
                            "task_id": task.get("id", idx),
                            "error": str(e)
                        },
                        source="synthesis_orchestrator"
                    )
                    
                    self._log(plan_id, f"Task {task.get('id', idx)} failed: {e}")
                    
                    # Check if we should continue or abort
                    if task.get("critical", False):
                        raise Exception(f"Critical task failed: {e}")
                    else:
                        results.append({"error": str(e), "task_id": task.get("id", idx)})
            
            # Update status to completed
            self.active_plans[plan_id]["status"] = "completed"
            self.active_plans[plan_id]["end_time"] = time.time()
            
            # Store results
            self.execution_results[plan_id] = {
                "status": "completed",
                "results": results,
                "completed_tasks": len(self.active_plans[plan_id]["completed_tasks"]),
                "failed_tasks": len(self.active_plans[plan_id]["failed_tasks"]),
                "duration": self.active_plans[plan_id]["end_time"] - self.active_plans[plan_id]["start_time"]
            }
            
            # Trigger Self-Reflection
            try:
                reflection = synthesis_model.reflect_on_execution(
                    plan,
                    self.execution_logs.get(plan_id, []),
                    self.execution_results.get(plan_id, {}).get("results", [])
                )
                self.execution_results[plan_id]["reflection"] = reflection
                self._log(plan_id, "Self-reflection completed")
            except Exception as e:
                self._log(plan_id, f"Self-reflection failed: {e}")

            # Emit plan completed event
            self.event_bus.emit_sync(
                self.EventType.WORKFLOW_COMPLETED,
                {
                    "plan_id": plan_id,
                    "status": "completed",
                    "completed_tasks": len(self.active_plans[plan_id]["completed_tasks"]),
                    "failed_tasks": len(self.active_plans[plan_id]["failed_tasks"]),
                    "reflection_summary": self.execution_results[plan_id].get("reflection", {}).get("insights", [])[:3]
                },
                source="synthesis_orchestrator"
            )
            
            return self.execution_results[plan_id]
            
        except Exception as e:
            # Update status to failed
            self.active_plans[plan_id]["status"] = "failed"
            self.active_plans[plan_id]["error"] = str(e)
            
            # Emit plan error event
            self.event_bus.emit_sync(
                self.EventType.SYSTEM_ERROR,
                {
                    "plan_id": plan_id,
                    "error": str(e)
                },
                source="synthesis_orchestrator"
            )
            
            return {
                "status": "failed",
                "error": str(e),
                "completed_tasks": len(self.active_plans[plan_id]["completed_tasks"]),
                "failed_tasks": len(self.active_plans[plan_id]["failed_tasks"])
            }
    
    async def _check_dependencies(self, plan_id: str, task: Dict[str, Any]) -> bool:
        """Check if task dependencies are satisfied."""
        depends_on = task.get("depends_on", [])
        if not depends_on:
            return True
        
        completed = self.active_plans[plan_id]["completed_tasks"]
        return all(dep in completed for dep in depends_on)
    
    async def _execute_task(self, plan_id: str, task: Dict[str, Any]) -> Any:
        """
        Execute a single task using dynamic tool lookup.
        
        Args:
            plan_id: Plan identifier
            task: Task definition
            
        Returns:
            Task execution result
        """
        from agent_fabric.tools import ALL_TOOLS

        agent = task.get("agent", "Operator")
        tool_name = task.get("tool", "unknown").lower()
        params = task.get("params", {})
        
        self._log(plan_id, f"Routing to agent: {agent}, tool: {tool_name}")
        
        try:
            # 1. Find the tool
            target_tool = None
            for tool in ALL_TOOLS:
                if tool.name.lower() == tool_name:
                    target_tool = tool
                    break

            # Fuzzy fallback if exact match fails
            if not target_tool:
                for tool in ALL_TOOLS:
                    if tool_name in tool.name.lower():
                        target_tool = tool
                        break

            if not target_tool:
                raise ValueError(f"Tool '{tool_name}' not found in registry.")

            # 2. Execute the tool
            # LangChain tools use .invoke() and handle args parsing
            # We map the raw params dict to what invoke expects

            self._log(plan_id, f"Invoking tool: {target_tool.name}")
            result_content = target_tool.invoke(params)

            return {
                "agent": agent,
                "tool": target_tool.name,
                "status": "completed",
                "output": str(result_content)
            }

        except Exception as e:
            self._log(plan_id, f"Error executing tool {tool_name}: {str(e)}")
            raise e
    
    def _log(self, plan_id: str, message: str):
        """Add log entry for plan execution."""
        if plan_id not in self.execution_logs:
            self.execution_logs[plan_id] = []
        
        log_entry = f"[{time.strftime('%H:%M:%S')}] {message}"
        self.execution_logs[plan_id].append(log_entry)
        print(f"[SYNTHESIS:{plan_id[:8]}] {message}")

        # Emit log event for real-time dashboard updates
        self.event_bus.emit_sync(
            self.EventType.SYSTEM_EVENT,
            {
                "plan_id": plan_id,
                "action": "log",
                "message": message
            },
            source="synthesis_orchestrator"
        )
    
    def get_plan_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a plan."""
        if plan_id not in self.active_plans:
            return None
        
        plan_state = self.active_plans[plan_id]
        return {
            "plan_id": plan_id,
            "status": plan_state["status"],
            "current_task": plan_state.get("current_task"),
            "completed_tasks": len(plan_state["completed_tasks"]),
            "failed_tasks": len(plan_state["failed_tasks"]),
            "total_tasks": len(plan_state["plan"].get("subtasks", [])),
            "logs": self.execution_logs.get(plan_id, [])[-10:]  # Last 10 logs
        }
    
    def list_active_plans(self) -> List[Dict[str, Any]]:
        """List all active plans."""
        return [
            {
                "plan_id": plan_id,
                "status": state["status"],
                "task_analysis": state["plan"].get("task_analysis", ""),
                "progress": f"{len(state['completed_tasks'])}/{len(state['plan'].get('subtasks', []))}"
            }
            for plan_id, state in self.active_plans.items()
        ]
    
    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel an active plan."""
        if plan_id not in self.active_plans:
            return False
        
        self.active_plans[plan_id]["status"] = "cancelled"
        
        # Emit cancellation event
        self.event_bus.emit_sync(
            self.EventType.WORKFLOW_COMPLETED,
            {
                "plan_id": plan_id,
                "status": "cancelled"
            },
            source="synthesis_orchestrator"
        )
        
        self._log(plan_id, "Plan cancelled by user")
        return True


# Global instances
synthesis_model = SynthesisThinkingModel()
execution_orchestrator = ExecutionOrchestrator()


def synthesize_task(user_request: str) -> Dict[str, Any]:
    """Main entry point for task synthesis with risk assessment."""
    return synthesis_model.decompose_task(user_request)

def reflect_on_execution(plan: Dict[str, Any], execution_log: List[str], actual_results: Any) -> Dict[str, Any]:
    """Main entry point for execution reflection."""
    return synthesis_model.reflect_on_execution(plan, execution_log, actual_results)

async def execute_synthesis_plan(plan: Dict[str, Any], plan_id: Optional[str] = None) -> Dict[str, Any]:
    """Main entry point for plan execution."""
    return await execution_orchestrator.execute_plan(plan, plan_id)

def get_plan_status(plan_id: str) -> Optional[Dict[str, Any]]:
    """Get status of an executing plan."""
    return execution_orchestrator.get_plan_status(plan_id)

def list_active_plans() -> List[Dict[str, Any]]:
    """List all active synthesis plans."""
    return execution_orchestrator.list_active_plans()

async def cancel_plan(plan_id: str) -> bool:
    """Cancel an executing plan."""
    return await execution_orchestrator.cancel_plan(plan_id)
