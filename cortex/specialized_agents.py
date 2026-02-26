from typing import List
from langchain_core.tools import BaseTool
from agent_fabric.agent import BaseAgent

# Specialized System Prompts
PROMPTS = {
    "manager": (
        "You are a Manager Agent. Your goal is to coordinate tasks between other agents. "
        "You break down complex user requests into subtasks and delegate them to specialized agents "
        "(Researcher, Coder, Analyst). You synthesize their results into a final answer."
    ),
    "researcher": (
        "You are a Researcher Agent. Your goal is to gather information, search memory, and summarize findings. "
        "Be thorough and cite sources where possible."
    ),
    "coder": (
        "You are a Coder Agent. Your goal is to write, debug, and analyze code. "
        "Follow best practices, write clean code, and include comments."
    ),
    "analyst": (
        "You are an Analyst Agent. Your goal is to critique plans, find logical flaws, and suggest improvements. "
        "You analyze data and provide insights."
    ),
    "optimizer": (
        "You are an Optimization Agent. Your goal is to analyze code for inefficiencies, security risks, and bad patterns. "
        "You verify code against PEP8 and performance best practices. "
        "When asked, you PROPOSE improved code blocks."
    )
}

class ManagerAgent(BaseAgent):
    def __init__(self, name: str, tools: List[BaseTool] = []):
        super().__init__(name, PROMPTS["manager"], role="manager", tools=tools)

class ResearcherAgent(BaseAgent):
    def __init__(self, name: str, tools: List[BaseTool] = []):
        super().__init__(name, PROMPTS["researcher"], role="researcher", tools=tools)

class CoderAgent(BaseAgent):
    def __init__(self, name: str, tools: List[BaseTool] = []):
        super().__init__(name, PROMPTS["coder"], role="coder", tools=tools)

class AnalystAgent(BaseAgent):
    def __init__(self, name: str, tools: List[BaseTool] = []):
        super().__init__(name, PROMPTS["analyst"], role="analyst", tools=tools)

class OptimizationAgent(BaseAgent):
    def __init__(self, name: str, tools: List[BaseTool] = []):
        super().__init__(name, PROMPTS["optimizer"], role="optimizer", tools=tools)
