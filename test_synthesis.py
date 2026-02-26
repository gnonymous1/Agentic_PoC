"""
Test Synthesis Thinking Model - Phase 3
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cortex.synthesis import (
    synthesize_task,
    execute_synthesis_plan,
    get_plan_status,
    list_active_plans
)


async def test_task_decomposition():
    """Test task decomposition"""
    print("\\n=== Testing Task Decomposition ===")
    
    try:
        # Test simple task
        plan = synthesize_task("Calculate fibonacci(10)")
        
        print(f"  [INFO] Task Analysis: {plan.get('task_analysis', '')}")
        print(f"  [INFO] Subtasks: {len(plan.get('subtasks', []))}")
        
        if plan.get("subtasks"):
            print("  [PASS] Task decomposition successful")
            for idx, task in enumerate(plan.get("subtasks", [])[:3]):
                print(f"    - Task {idx+1}: {task.get('description', '')[:50]}")
        else:
            print("  [FAIL] No subtasks generated")
            return False
        
        # Check risk assessment
        if plan.get("risk_assessment"):
            print(f"  [PASS] Risk assessment present")
            print(f"    - Overall Score: {plan['risk_assessment'].get('overall_score', 0):.2f}")
            print(f"    - Severity: {plan['risk_assessment'].get('severity', 'unknown')}")
        else:
            print("  [WARN] No risk assessment")
        
        return True
        
    except Exception as e:
        print(f"  [FAIL] Task decomposition failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_plan_execution():
    """Test plan execution"""
    print("\\n=== Testing Plan Execution ===")
    
    try:
        # Create a simple plan
        plan = {
            "task_analysis": "Test plan execution",
            "subtasks": [
                {
                    "id": 1,
                    "description": "Step 1: Initialize",
                    "agent": "Operator",
                    "tool": "test_tool",
                    "params": {},
                    "depends_on": []
                },
                {
                    "id": 2,
                    "description": "Step 2: Process",
                    "agent": "Coder",
                    "tool": "python_exec",
                    "params": {"code": "print('test')"},
                    "depends_on": [1]
                },
                {
                    "id": 3,
                    "description": "Step 3: Finalize",
                    "agent": "Operator",
                    "tool": "test_tool",
                    "params": {},
                    "depends_on": [2]
                }
            ]
        }
        
        print("  [INFO] Executing plan with 3 tasks...")
        result = await execute_synthesis_plan(plan, plan_id="test_plan_001")
        
        if result.get("status") == "completed":
            print("  [PASS] Plan execution completed")
            print(f"    - Completed Tasks: {result.get('completed_tasks', 0)}")
            print(f"    - Failed Tasks: {result.get('failed_tasks', 0)}")
            print(f"    - Duration: {result.get('duration', 0):.2f}s")
            return True
        else:
            print(f"  [FAIL] Plan execution failed: {result.get('error', 'unknown')}")
            return False
        
    except Exception as e:
        print(f"  [FAIL] Plan execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_plan_status():
    """Test plan status tracking"""
    print("\\n=== Testing Plan Status Tracking ===")
    
    try:
        # List active plans
        plans = list_active_plans()
        print(f"  [INFO] Active plans: {len(plans)}")
        
        if plans:
            # Get status of first plan
            plan_id = plans[0]["plan_id"]
            status = get_plan_status(plan_id)
            
            if status:
                print("  [PASS] Plan status retrieval successful")
                print(f"    - Plan ID: {plan_id[:16]}...")
                print(f"    - Status: {status.get('status', 'unknown')}")
                print(f"    - Progress: {status.get('completed_tasks', 0)}/{status.get('total_tasks', 0)}")
                return True
            else:
                print("  [FAIL] Could not retrieve plan status")
                return False
        else:
            print("  [PASS] No active plans (expected after completion)")
            return True
        
    except Exception as e:
        print(f"  [FAIL] Plan status test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_complex_task():
    """Test complex task decomposition"""
    print("\\n=== Testing Complex Task Decomposition ===")
    
    try:
        # Test complex task
        plan = synthesize_task("Create a web scraper to fetch news articles from BBC and save to CSV")
        
        print(f"  [INFO] Task Analysis: {plan.get('task_analysis', '')[:100]}...")
        print(f"  [INFO] Subtasks: {len(plan.get('subtasks', []))}")
        
        if len(plan.get("subtasks", [])) >= 3:
            print("  [PASS] Complex task decomposed into multiple steps")
            
            # Show first few tasks
            for idx, task in enumerate(plan.get("subtasks", [])[:5]):
                print(f"    {idx+1}. {task.get('description', '')[:60]}")
                print(f"       Agent: {task.get('agent', 'unknown')}, Tool: {task.get('tool', 'unknown')}")
            
            # Check dependencies
            has_deps = any(task.get("depends_on") for task in plan.get("subtasks", []))
            if has_deps:
                print("  [PASS] Task dependencies identified")
            else:
                print("  [WARN] No task dependencies found")
            
            return True
        else:
            print("  [FAIL] Insufficient task decomposition")
            return False
        
    except Exception as e:
        print(f"  [FAIL] Complex task test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all Phase 3 Synthesis tests"""
    print("\\n" + "="*60)
    print("Phase 3 Synthesis Thinking Model Tests")
    print("="*60)
    
    results = {
        "Task Decomposition": await test_task_decomposition(),
        "Plan Execution": await test_plan_execution(),
        "Plan Status": await test_plan_status(),
        "Complex Task": await test_complex_task()
    }
    
    print("\\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\\n" + "="*60)
    if all_passed:
        print("[SUCCESS] All Synthesis tests passed!")
        print("\\nNext steps:")
        print("1. Test synthesis via API: POST /synthesis/plan")
        print("2. Execute plans: POST /synthesis/plans/execute")
        print("3. Monitor status: GET /synthesis/plans/{plan_id}")
    else:
        print("[WARNING] Some tests failed. Review errors above.")
    print("="*60 + "\\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
