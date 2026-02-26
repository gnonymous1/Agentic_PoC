import time
from hippocampus.memory import Hippocampus
from cortex.llm import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

class MemoryConsolidator:
    def __init__(self):
        self.memory = Hippocampus()
        self.llm = get_llm(role="thinker") # DeepSeek for reasoning

    def consolidate(self):
        """
        Runs a nightly consolidation process (simulated).
        1. Reads recent memories.
        2. Synthesizes them into 'Principles'.
        3. Stores principles back into memory.
        """
        print("[Consolidator] Starting nightly dreaming process...")
        
        # In a real app, query by timestamp. For PoC, take all.
        recent_memories = self.memory.recall("learned", n_results=10)
        
        if not recent_memories:
            print("[Consolidator] No new memories to process.")
            return

        memory_text = "\n".join([m['content'] for m in recent_memories])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are the 'Dreamer'. Your job is to analyze raw memories of the day and distill them into "
                       "general principles or wisdom. discard noise. "
                       "Input: Raw logs/memories. "
                       "Output: A list of 3-5 high-level principles to remember forever."),
            ("human", f"Memories:\n{memory_text}")
        ])
        
        chain = prompt | self.llm | StrOutputParser()
        wisdom = chain.invoke({})
        
        print(f"[Consolidator] Distilled Wisdom:\n{wisdom}")
        
        # Store the wisdom
        self.memory.remember(wisdom, {"type": "principle", "source": "dreamer"})
        print("[Consolidator] Wisdom stored in long-term memory.")

if __name__ == "__main__":
    # Manual trigger for testing
    dreamer = MemoryConsolidator()
    dreamer.consolidate()
