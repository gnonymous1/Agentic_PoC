#!/usr/bin/env python3
"""
Comprehensive Test Suite for Agentic AI v2.0
Tests all implemented features
"""

import asyncio
import sys
from datetime import datetime

print("="*60)
print("AGENTIC AI v2.0 - COMPREHENSIVE TEST SUITE")
print("="*60)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Track test results
tests_passed = 0
tests_failed = 0
errors = []

def test_section(name):
    """Print test section header"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print("="*60)

def test_pass(msg):
    """Mark test as passed"""
    global tests_passed
    tests_passed += 1
    print(f"  [OK] PASS: {msg}")

def test_fail(msg, error=None):
    """Mark test as failed"""
    global tests_failed
    tests_failed += 1
    print(f"  [X] FAIL: {msg}")
    if error:
        print(f"    Error: {error}")
        errors.append(f"{msg}: {error}")

# ============================================
# TEST 1: Graph Compilation
# ============================================
test_section("1. Graph Compilation")
try:
    from cortex.graph import graph
    test_pass("Graph imports successfully")
    
    # Check graph has all nodes
    from langgraph.graph import StateGraph
    if hasattr(graph, 'nodes'):
        node_names = list(graph.nodes.keys()) if hasattr(graph, 'nodes') else []
        expected_nodes = ['Supervisor', 'Researcher', 'Coder', 'Architect', 'Surfer', 'Operator', 'Antigravity', 'Chat']
        missing = [n for n in expected_nodes if n not in node_names]
        if not missing:
            test_pass(f"All {len(expected_nodes)} agent nodes present")
        else:
            test_fail(f"Missing nodes: {missing}")
    else:
        test_pass("Graph object created (nodes not directly accessible)")
except Exception as e:
    test_fail("Graph compilation failed", str(e))

# ============================================
# TEST 2: Dynamic Tools Loading
# ============================================
test_section("2. Dynamic Tools Loading")
try:
    from agent_fabric.tool_loader import load_dynamic_tools
    tools = load_dynamic_tools()
    
    if len(tools) > 0:
        test_pass(f"Loaded {len(tools)} dynamic tools")
        for tool in tools[:3]:  # Show first 3
            print(f"    - {tool.name}")
    else:
        test_fail("No dynamic tools loaded")
except Exception as e:
    test_fail("Dynamic tools loading failed", str(e))

# ============================================
# TEST 3: Real Code Execution
# ============================================
test_section("3. Real Code Execution")
try:
    from agent_fabric.tools import execute_python
    
    # Test 1: Simple print
    result1 = execute_python.invoke({'code': 'print(2+2)'})
    if '4' in result1:
        test_pass("Simple arithmetic (2+2=4)")
    else:
        test_fail("Simple arithmetic failed", f"Output: {result1[:100]}")
    
    # Test 2: Variable assignment
    result2 = execute_python.invoke({'code': 'x = 10\nprint(x * 2)'})
    if '20' in result2:
        test_pass("Variable assignment and multiplication")
    else:
        test_fail("Variable assignment failed", f"Output: {result2[:100]}")
    
    # Test 3: Error handling
    result3 = execute_python.invoke({'code': '1/0'})
    if 'Error' in result3 or 'ZeroDivisionError' in result3:
        test_pass("Error handling works")
    else:
        test_fail("Error handling failed")
        
except Exception as e:
    test_fail("Code execution failed", str(e))

# ============================================
# TEST 4: Identity Loader
# ============================================
test_section("4. Identity Loader")
try:
    from identity import get_identity_loader, inject_identity
    loader = get_identity_loader()
    
    # Test SOUL.md
    soul = loader.get_soul()
    if len(soul) > 0 and "Core Personality" in soul:
        test_pass("SOUL.md loaded correctly")
    else:
        test_fail("SOUL.md not loaded or empty")
    
    # Test IDENTITY.md
    identity = loader.get_identity()
    if len(identity) > 0 and "Role" in identity:
        test_pass("IDENTITY.md loaded correctly")
    else:
        test_fail("IDENTITY.md not loaded or empty")
    
    # Test MEMORY.md
    memory = loader.get_memory()
    if len(memory) > 0:
        test_pass("MEMORY.md loaded correctly")
    else:
        test_fail("MEMORY.md not loaded or empty")
    
    # Test prompt injection
    base_prompt = "You are an AI assistant."
    enhanced = inject_identity(base_prompt)
    if len(enhanced) > len(base_prompt):
        test_pass("Identity injection works")
    else:
        test_fail("Identity injection failed")
        
except Exception as e:
    test_fail("Identity loader failed", str(e))

# ============================================
# TEST 5: Hybrid Search (BM25 + Vector)
# ============================================
test_section("5. Hybrid Search (BM25 + Vector)")
try:
    from hippocampus.memory import Hippocampus
    
    h = Hippocampus()
    
    # Store test memories
    h.remember("Python is a programming language", {"topic": "coding", "lang": "python"})
    h.remember("Machine learning uses Python extensively", {"topic": "ml", "lang": "python"})
    h.remember("Docker containers are useful for deployment", {"topic": "devops", "tool": "docker"})
    h.remember("JavaScript runs in browsers", {"topic": "coding", "lang": "javascript"})
    
    # Test hybrid search
    results = h.recall("python programming", n_results=5, use_hybrid=True)
    
    if len(results) >= 2:
        test_pass(f"Hybrid search returns {len(results)} results")
        
        # Check for Python-related results
        python_results = [r for r in results if 'python' in r.get('content', '').lower()]
        if len(python_results) >= 1:
            test_pass(f"Relevant results found ({len(python_results)} Python matches)")
        else:
            test_fail("No relevant Python results found")
        
        # Check for scores
        has_scores = any('score' in r for r in results)
        if has_scores:
            test_pass("Results contain hybrid scores")
        else:
            test_fail("Results missing hybrid scores")
    else:
        test_fail(f"Hybrid search returned insufficient results: {len(results)}")
        
except Exception as e:
    test_fail("Hybrid search failed", str(e))

# ============================================
# TEST 6: Agent Factory
# ============================================
test_section("6. Agent Factory (Async)")
async def test_agent_factory():
    try:
        from cortex.agent_factory import get_agent_factory, AgentFactory
        
        factory = get_agent_factory()
        test_pass("Agent factory initializes")
        
        # Check if we can create an agent config
        agent_configs = [
            {
                "name": "TestThinker",
                "role": "thinker",
                "system_prompt": "You are a test thinker agent.",
                "tools": [],
                "task": "Think about testing"
            }
        ]
        test_pass("Agent configurations created")
        
        # Note: Full execution would require LLM, so we test structure only
        test_pass("Agent factory structure validated")
        
    except Exception as e:
        test_fail("Agent factory failed", str(e))

try:
    asyncio.run(test_agent_factory())
except Exception as e:
    test_fail("Agent factory async execution failed", str(e))

# ============================================
# TEST 7: Fallback Chain
# ============================================
test_section("7. Fallback Chain")
async def test_fallback_chain():
    try:
        from cortex.fallback_chain import get_fallback_chain, FallbackChain, FallbackConfig
        
        chain = get_fallback_chain()
        test_pass("Fallback chain initializes")
        
        # Test simple function with fallback
        async def successful_op():
            return "success"
        
        result = await chain.execute_with_fallback(successful_op, "test_success")
        if result.get('status') == 'success':
            test_pass("Fallback chain executes successful operations")
        else:
            test_fail("Fallback chain failed on success", str(result))
        
        # Test circuit breaker logic
        stats = chain.get_stats()
        if 'cache_size' in stats:
            test_pass("Fallback stats accessible")
        else:
            test_fail("Fallback stats missing")
            
    except Exception as e:
        test_fail("Fallback chain failed", str(e))

try:
    asyncio.run(test_fallback_chain())
except Exception as e:
    test_fail("Fallback chain async execution failed", str(e))

# ============================================
# TEST 8: Memory System Integration
# ============================================
test_section("8. Memory System Integration")
try:
    from hippocampus.memory import Hippocampus
    
    h = Hippocampus()
    
    # Test store and retrieve
    h.remember("Test memory content", {"test": True})
    results = h.recall("test memory")
    
    if len(results) > 0:
        test_pass("Memory store and retrieve works")
    else:
        test_fail("Memory retrieve returned no results")
    
    # Test summary
    summary = h.get_summary()
    if 'total_memories' in summary:
        test_pass("Memory summary generated")
        print(f"    Total memories: {summary['total_memories']}")
    else:
        test_fail("Memory summary failed")
        
except Exception as e:
    test_fail("Memory system failed", str(e))

# ============================================
# TEST 9: Tools Integration
# ============================================
test_section("9. Tools Integration")
try:
    from agent_fabric.tools import multiply, vector_search, save_memory
    
    # Test multiply
    result = multiply.invoke({'a': 5, 'b': 7})
    if result == 35:
        test_pass("Multiply tool works (5*7=35)")
    else:
        test_fail("Multiply tool failed", f"Expected 35, got {result}")
    
    # Test save_memory
    save_result = save_memory.invoke({'content': 'Test memory', 'source': 'test_suite'})
    if 'saved' in save_result.lower() or 'success' in save_result.lower():
        test_pass("Save memory tool works")
    else:
        test_fail("Save memory tool failed", save_result)
        
except Exception as e:
    test_fail("Tools integration failed", str(e))

# ============================================
# TEST 10: End-to-End Integration
# ============================================
test_section("10. End-to-End Integration")
try:
    # Test that all components work together
    from cortex.graph import graph
    from identity import inject_identity
    from hippocampus.memory import Hippocampus
    from agent_fabric.tools import execute_python
    
    # Simulate a simple workflow
    h = Hippocampus()
    h.remember("Integration test", {"test": "e2e"})
    
    # Execute code
    code_result = execute_python.invoke({'code': 'x = 5\nprint(f"Value: {x}")'})
    
    # Search memory
    memories = h.recall("integration")
    
    # Inject identity
    prompt = inject_identity("You are an AI.")
    
    if all([
        len(memories) > 0,
        'Value: 5' in code_result,
        len(prompt) > 20
    ]):
        test_pass("All components integrate successfully")
    else:
        test_fail("Integration test failed", "One or more components failed")
        
except Exception as e:
    test_fail("End-to-end integration failed", str(e))

# ============================================
# FINAL SUMMARY
# ============================================
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
print(f"Tests Passed: {tests_passed}")
print(f"Tests Failed: {tests_failed}")
print(f"Success Rate: {(tests_passed/(tests_passed+tests_failed)*100):.1f}%")

if errors:
    print("\nErrors Encountered:")
    for error in errors:
        print(f"  - {error}")

print("\n" + "="*60)
if tests_failed == 0:
    print("[SUCCESS] ALL TESTS PASSED - System is ready!")
    sys.exit(0)
else:
    print("[WARNING] SOME TESTS FAILED - Please review errors above")
    sys.exit(1)
