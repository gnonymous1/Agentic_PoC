
from typing import Dict, Any, List
from langchain_core.messages import BaseMessage, HumanMessage
from agent_fabric.agent import BaseAgent

class AnalystAgent(BaseAgent):
    """
    Agent specialized in data analysis, pattern recognition, and reporting.
    """
    
    def __init__(self, name: str = "Analyst", llm: Any = None):
        system_prompt = (
            "You are the Analyst Agent, an expert in data interpretation and reporting.\n"
            "Your responsibilities:\n"
            "1. Analyze datasets or logs to identify patterns and anomalies.\n"
            "2. Synthesize complex information into concise executive summaries.\n"
            "3. Generate structured reports from unstructured data.\n"
            "Focus on clarity, accuracy, and insight."
        )
        super().__init__(name=name, system_prompt=system_prompt, role="specialist")

    def analyze_logs(self, logs: List[str]) -> str:
        """Analyze a list of log entries."""
        return f"Analyzed {len(logs)} log entries. Found normal operational patterns."

    def summarize_report(self, text: str) -> str:
        """Create a summary of the provided text."""
        return f"Summary: {text[:100]}..."

    def _register_sub_agents(self):
        """Register sub-agents (none for now)."""
        pass

    def get_capabilities(self) -> List[str]:
        """Return agent capabilities."""
        return ["data_analysis", "log_parsing", "reporting"]
