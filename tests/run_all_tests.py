import subprocess
import sys
import os

TEST_SCRIPTS = [
    "tests/test_observability_phase1.py",
    "tests/test_resilience_phase2.py",
    "tests/test_performance_phase3.py",
    "tests/test_learning_phase4.py",
    "tests/test_reasoning_phase5.py",
    "tests/test_human_loop_phase6.py",
    "tests/test_tool_fabric_phase7.py",
    "tests/test_multi_device_phase8.py",
    "tests/test_sandbox_phase8.py", # Security (Phase 9)
    "tests/test_marketplace_phase10.py",
    "tests/test_revenue_phase11.py",
    "tests/test_evolution_phase12.py",
    "tests/test_cost_tracker.py",
]

def run_all_tests():
    print("="*60)
    print("      OMNIOS 4.0 MASTER VERIFICATION SUITE      ")
    print("="*60)
    
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    
    passed = 0
    failed = 0
    
    for script in TEST_SCRIPTS:
        print(f"\n[RUNNING] {script}...")
        try:
            result = subprocess.run(
                [sys.executable, script],
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"[PASS] {script}")
                passed += 1
            else:
                print(f"[FAIL] {script}")
                print(result.stdout)
                print(result.stderr)
                failed += 1
                
        except Exception as e:
            print(f"[ERROR] {script}: {e}")
            failed += 1
            
    print("\n" + "="*60)
    print(f"VERIFICATION COMPLETE")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*60)

if __name__ == "__main__":
    run_all_tests()
