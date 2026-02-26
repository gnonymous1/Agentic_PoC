import subprocess
import sys
import os
import time

# List of tests to run in order
# (script_path, description, timeout)
TEST_SUITE = [
    ("test_phase1.py", "Phase 1: Foundation (EventBus/Database)", 30),
    ("test_phase2.py", "Phase 2: Omni-Channel (Gateway/WebSockets)", 30),
    ("tests/test_agent_collab_phase5.py", "Phase 5: Multi-Agent Collaboration", 60),
    ("tests/test_learning.py", "Phase 6.1: Reinforcement Learning", 30),
    ("tests/test_optimization.py", "Phase 6.2: Code Optimization", 45),
    ("tests/test_microservices.py", "Phase 6.3: Microservices Infrastructure", 30),
    ("tests/test_voice.py", "Phase 7: Voice Interface (STT/TTS)", 30)
]

def run_test(script, description, timeout):
    print(f"\n{'='*60}")
    print(f"RUNNING: {description}")
    print(f"SCRIPT:  {script}")
    print(f"{'='*60}")
    
    start_time = time.time()
    try:
        # Use sys.executable to ensure we use the same python interpreter
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd() # Run from project root
        )
        duration = time.time() - start_time
        
        print("\n--- OUTPUT ---")
        # Print a snippet of logs to keep output clean, or full if fail
        if result.returncode == 0:
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            print(f"\n[PASS] {description} (Time: {duration:.2f}s)")
            return True, result.stdout
        else:
            print(result.stdout)
            print("--- ERROR ---")
            print(result.stderr)
            print(f"\n[FAIL] {description} (Return Code: {result.returncode})")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        print(f"\n[FAIL] {description} (TIMEOUT after {timeout}s)")
        return False, "Timeout"
    except Exception as e:
        print(f"\n[FAIL] {description} (Exception: {str(e)})")
        return False, str(e)

def main():
    print(">>> AgentOS Comprehensive System Verification <<<")
    print(f"Detected Platform: {sys.platform}")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"Project Root: {os.getcwd()}")
    
    results = []
    
    for script, desc, timeout in TEST_SUITE:
        if not os.path.exists(script):
            print(f"\n[ERROR] Test script not found: {script}")
            results.append((desc, False, "File Not Found"))
            continue
            
        success, output = run_test(script, desc, timeout)
        results.append((desc, success, output))
        
        # Small cooldown to allow port release etc.
        time.sleep(2)
        
    # Final Report
    print(f"\n\n{'#'*60}")
    print("VERIFICATION SUMMARY")
    print(f"{'#'*60}")
    
    all_passed = True
    for desc, success, _ in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status} | {desc}")
        if not success:
            all_passed = False
            
    print(f"{'#'*60}")
    
    if all_passed:
        print("\n>>> SYSTEM STATUS: GREEN (Ready for Operation) <<<")
        sys.exit(0)
    else:
        print("\n>>> SYSTEM STATUS: RED (Verification Failed) <<<")
        sys.exit(1)

if __name__ == "__main__":
    main()
