from typing import TypedDict, Annotated, List, Union
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    The shared state of the Agentic Mesh.
    """
    # The conversation history (Messages)
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Critical: The 'Scratchpad' or 'Blackboard'
    # Agents write their intermediate findings here
    blackboard: dict
    
    # The current plan / sub-tasks
    # structured as a list of steps
    plan: List[str]
    
    # Metadata for debugging and evolution
    # e.g., {"step_1": {"agent": "Researcher", "duration": 2.5}}
    meta_data: dict
