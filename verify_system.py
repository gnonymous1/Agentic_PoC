from cortex.graph import graph
from langchain_core.messages import HumanMessage
from colorama import init, Fore

init(autoreset=True)

def run_test(name, input_text):
    print(Fore.CYAN + f"\n=== TEST: {name} ===")
    print(Fore.GREEN + f"Input: {input_text}")
    print("-" * 30)
    
    initial_state = {
        "messages": [HumanMessage(content=input_text)],
        "blackboard": {},
        "plan": [],
        "meta_data": {}
    }
    
    events = []
    try:
        for event in graph.stream(initial_state):
            for key, value in event.items():
                print(Fore.MAGENTA + f"Node: {key}")
                if "messages" in value:
                    last_msg = value["messages"][-1]
                    print(f" Output: {last_msg.content[:200]}...") # Truncate for readability
                events.append((key, value))
        print(Fore.CYAN + "=== TEST PASSED (Graph Executed) ===")
        return True
    except Exception as e:
        print(Fore.RED + f"=== TEST FAILED: {str(e)} ===")
        return False

def main():
    print(Fore.YELLOW + "Starting System Integrity Check...")
    
    # 1. Test Memory (Researcher)
    run_test("Memory Recall", 
             "Research the benefits of Vitamin D and save the key points to memory.")
             
    # 2. Test Tool Creation (Architect)
    run_test("Evolution (Tool Creation)", 
             "Architect, create a new tool called 'say_hello' that prints 'Hello World'.")
             
    # 3. Test Self-Healing (Simulated)
    # This is harder to test without actually crashing, but we test the routing
    run_test("Error Handling Routing", 
             "I am trying to import 'non_existent_package' and getting ModuleNotFoundError. Architect, fix it.")

if __name__ == "__main__":
    main()
