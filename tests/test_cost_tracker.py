import sys
import os
from datetime import datetime
from collections import defaultdict

# Ensure we can import from core
# Assuming the script is run from the root of the repo or tests/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.monitoring import CostTracker

def test_cost_tracker():
    print("Testing CostTracker...")

    tracker = CostTracker()

    # Test 1: Initial State
    # Verify initialized structures
    if isinstance(tracker.daily_costs, defaultdict) and len(tracker.daily_costs) == 0:
         print("PASS: Initial state correct")
    else:
         print("FAIL: Initial state incorrect")

    # Record a cost
    # input_tokens: 1000, output_tokens: 1000
    # cost_per_1k_input: 0.01, cost_per_1k_output: 0.03
    # expected cost: (1000/1000)*0.01 + (1000/1000)*0.03 = 0.01 + 0.03 = 0.04
    tracker.record_cost(
        provider="openai",
        model="gpt-4",
        input_tokens=1000,
        output_tokens=1000,
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.03,
        agent="researcher",
        task_type="analysis"
    )

    today = datetime.now().strftime("%Y-%m-%d")

    # Check daily cost
    daily = tracker.get_daily_spend()
    expected_cost = 0.04
    if abs(daily - expected_cost) < 0.0001:
        print(f"PASS: Daily cost calculation (Expected: {expected_cost}, Got: {daily})")
    else:
        print(f"FAIL: Daily cost calculation (Expected: {expected_cost}, Got: {daily})")
        return

    # Check provider cost
    provider_cost = tracker.per_provider_costs["openai"]
    if abs(provider_cost - expected_cost) < 0.0001:
        print("PASS: Provider cost aggregation")
    else:
        print(f"FAIL: Provider cost aggregation (Expected: {expected_cost}, Got: {provider_cost})")

    # Check agent cost
    agent_cost = tracker.per_agent_costs["researcher"]
    if abs(agent_cost - expected_cost) < 0.0001:
        print("PASS: Agent cost aggregation")
    else:
        print(f"FAIL: Agent cost aggregation (Expected: {expected_cost}, Got: {agent_cost})")

    # Check task cost
    task_cost = tracker.per_task_costs["analysis"]
    if abs(task_cost - expected_cost) < 0.0001:
        print("PASS: Task cost aggregation")
    else:
        print(f"FAIL: Task cost aggregation (Expected: {expected_cost}, Got: {task_cost})")

    # Record another cost to verify accumulation
    # input: 500, output: 0
    # cost: (500/1000)*0.01 = 0.005
    tracker.record_cost(
        provider="openai",
        model="gpt-4",
        input_tokens=500,
        output_tokens=0,
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.03,
        agent="writer",
        task_type="writing"
    )

    expected_total = 0.04 + 0.005
    daily = tracker.get_daily_spend()
    if abs(daily - expected_total) < 0.0001:
        print(f"PASS: Cost accumulation (Expected: {expected_total}, Got: {daily})")
    else:
        print(f"FAIL: Cost accumulation (Expected: {expected_total}, Got: {daily})")

    # Check Cost Report
    report = tracker.get_cost_report()
    # Cost Report rounds to 4 decimals
    if report["today_usd"] == round(expected_total, 4):
        print("PASS: Cost report today_usd")
    else:
         print(f"FAIL: Cost report today_usd (Expected: {round(expected_total, 4)}, Got: {report['today_usd']})")

    if len(report["last_10_calls"]) == 2:
        print("PASS: Cost history tracking")
    else:
        print(f"FAIL: Cost history tracking (Expected 2 items, got {len(report['last_10_calls'])})")

if __name__ == "__main__":
    test_cost_tracker()
