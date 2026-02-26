import pytest
from unittest.mock import MagicMock, patch
from core.coordinator import CoordinatorAgent

@pytest.fixture
def coordinator():
    with patch("core.coordinator.ObservabilityEngine"), \
         patch("core.coordinator.LLMRouter"), \
         patch("core.coordinator.VectorMemory"), \
         patch("core.coordinator.AdaptiveLearningEngine"), \
         patch("core.coordinator.AdvancedReasoningEngine"), \
         patch("core.coordinator.HumanInteractionManager"), \
         patch("core.coordinator.DeviceManager"), \
         patch("core.coordinator.UsageQuotaManager"), \
         patch("core.coordinator.MetaLearningEngine"), \
         patch("core.coordinator.SelfImprover"):

        config = {"test": "config"}
        agent = CoordinatorAgent(config)
        return agent

@pytest.mark.parametrize("action,expected", [
    ("delete file", True),
    ("remove user", True),
    ("wipe disk", True),
    ("format drive", True),
    ("terminate process", True),
    ("reboot system", True),
    ("DELETE ALL", True),
    ("Remove", True),
    ("delete_file", True),
    ("server_reboot", True),
    ("check status", False),
    ("create file", False),
    ("list directory", False),
    ("", False),
    (None, False),
])
def test_is_sensitive(coordinator, action, expected):
    task = {}
    if action is not None:
        task["action"] = action
    elif action is None:
        # Test case where action key exists but value is None
        # OR test case where action key is missing entirely
        # Let's test explicit None for now, and handle missing key separately if needed.
        # Wait, parameterized input (None, False) means action is None.
        # If action is None, task["action"] = None.
        task["action"] = None

    # Test missing key case separately or as another param

    try:
        assert coordinator._is_sensitive(task) == expected
    except AttributeError:
        pytest.fail(f"AttributeError raised for action: {action}")
    except Exception as e:
        pytest.fail(f"Exception raised: {e}")

def test_is_sensitive_missing_key(coordinator):
    task = {} # No "action" key
    assert coordinator._is_sensitive(task) == False
