import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.analyst_agent import AnalystAgent
from agent_fabric.agent import BaseAgent

@pytest.fixture
def mock_dependencies():
    """Fixture to mock external dependencies of BaseAgent."""
    with patch('agent_fabric.agent.get_llm') as mock_get_llm, \
         patch('agent_fabric.agent.registry') as mock_registry, \
         patch('agent_fabric.agent.EventBus') as mock_event_bus:

        # Setup mock returns
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance

        mock_bus_instance = MagicMock()
        mock_event_bus.get_sync.return_value = mock_bus_instance

        yield {
            'llm': mock_get_llm,
            'registry': mock_registry,
            'event_bus': mock_event_bus,
            'llm_instance': mock_llm_instance,
            'bus_instance': mock_bus_instance
        }

def test_initialization(mock_dependencies):
    """Test that AnalystAgent initializes correctly."""
    agent = AnalystAgent()

    assert agent.name == "Analyst"
    assert agent.role == "specialist"
    assert "Analyst Agent" in agent.system_prompt
    assert "expert in data interpretation" in agent.system_prompt

    # Verify dependencies were called
    mock_dependencies['llm'].assert_called_once()
    mock_dependencies['registry'].register_agent.assert_called_once()
    mock_dependencies['event_bus'].get_sync.assert_called_once()

def test_analyze_logs(mock_dependencies):
    """Test analyze_logs method."""
    agent = AnalystAgent()
    logs = ["Log entry 1", "Log entry 2", "Log entry 3"]

    result = agent.analyze_logs(logs)

    assert "Analyzed 3 log entries" in result
    assert "Found normal operational patterns" in result

def test_analyze_logs_empty(mock_dependencies):
    """Test analyze_logs with empty list."""
    agent = AnalystAgent()
    logs = []

    result = agent.analyze_logs(logs)

    assert "Analyzed 0 log entries" in result

def test_summarize_report_short(mock_dependencies):
    """Test summarize_report with short text."""
    agent = AnalystAgent()
    text = "Short report."

    result = agent.summarize_report(text)

    assert "Summary: Short report...." in result

def test_summarize_report_long(mock_dependencies):
    """Test summarize_report with long text (truncation)."""
    agent = AnalystAgent()
    text = "A" * 150

    result = agent.summarize_report(text)

    # Check that it starts with Summary:
    assert result.startswith("Summary: ")
    # Check length: "Summary: " (9 chars) + 100 chars + "..." (3 chars) = 112
    assert len(result) == 112
    assert result.endswith("...")
    assert "A" * 100 in result

def test_get_capabilities(mock_dependencies):
    """Test get_capabilities returns expected list."""
    agent = AnalystAgent()

    capabilities = agent.get_capabilities()

    expected_capabilities = ["data_analysis", "log_parsing", "reporting"]
    assert capabilities == expected_capabilities
