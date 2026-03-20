import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock everything that causes import errors
mock_langchain = MagicMock()
sys.modules['langchain_core'] = mock_langchain
sys.modules['langchain_core.messages'] = mock_langchain
sys.modules['langchain_core.prompts'] = mock_langchain
sys.modules['langchain_core.runnables'] = mock_langchain
sys.modules['langchain_core.tools'] = mock_langchain
sys.modules['langchain_openai'] = mock_langchain
sys.modules['langchain_google_genai'] = mock_langchain
sys.modules['langchain_groq'] = mock_langchain

# Mock pydantic
mock_pydantic = MagicMock()
class BaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    def dict(self):
        return self.__dict__
mock_pydantic.BaseModel = BaseModel
sys.modules['pydantic'] = mock_pydantic

# Mock cortex internal modules
sys.modules['cortex.llm'] = MagicMock()
sys.modules['cortex.registry'] = MagicMock()
sys.modules['cortex.events'] = MagicMock()
sys.modules['cortex.evolution.learning'] = MagicMock()
sys.modules['cortex.state'] = MagicMock()
sys.modules['cortex.agent_protocol'] = MagicMock()

from agents.security_agent import SecurityAgent

def test_security_agent_init():
    print("Running test_security_agent_init...")
    mock_llm = MagicMock()
    sys.modules['cortex.llm'].get_llm.return_value = mock_llm

    agent = SecurityAgent(name="TestSecurity")
    assert agent.name == "TestSecurity"
    assert agent.role == "specialist"
    assert "Security Agent" in agent.system_prompt
    sys.modules['cortex.llm'].get_llm.assert_called_with(role="specialist")
    print("test_security_agent_init passed!")

def test_scan_code():
    print("Running test_scan_code...")
    agent = SecurityAgent()
    test_code = "print('hello')"
    result = agent.scan_code(test_code)

    assert f"on {len(test_code)} bytes" in result
    assert "No critical CVEs found" in result
    assert "Architecture review" in result
    print("test_scan_code passed!")

def test_get_capabilities():
    print("Running test_get_capabilities...")
    agent = SecurityAgent()
    capabilities = agent.get_capabilities()

    assert "code_audit" in capabilities
    assert "vulnerability_scan" in capabilities
    assert "hardening" in capabilities
    print("test_get_capabilities passed!")

if __name__ == "__main__":
    try:
        test_security_agent_init()
        test_scan_code()
        test_get_capabilities()
        print("\nAll SecurityAgent tests passed successfully!")
    except Exception as e:
        print(f"\nTests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
