import importlib

import pytest

from core.device_manager import DeviceManager
from cortex.events import EventBus, EventType


@pytest.mark.baseline
def test_device_manager_registers_device():
    manager = DeviceManager()
    device_id = manager.register_device("cli", metadata={"source": "baseline"})

    assert device_id in manager.devices
    assert manager.devices[device_id].metadata["source"] == "baseline"


@pytest.mark.baseline
@pytest.mark.asyncio
async def test_event_bus_emit_and_history():
    bus = await EventBus.get()
    observed = []

    def _on_event(event):
        observed.append(event)

    bus.subscribe(EventType.SYSTEM_EVENT, _on_event)
    await bus.emit_async(EventType.SYSTEM_EVENT, {"ping": "pong"}, source="baseline-test")
    bus.unsubscribe(EventType.SYSTEM_EVENT, _on_event)

    assert observed
    assert observed[-1].data["ping"] == "pong"
    assert bus.get_history(EventType.SYSTEM_EVENT, limit=1)[0].data["ping"] == "pong"


@pytest.mark.baseline
def test_requirements_removed_invalid_ast_grep_pin():
    with open("requirements.txt", "r", encoding="utf-8") as requirements_file:
        requirements = requirements_file.read()

    assert "ast-grep==0.1.0" not in requirements


@pytest.mark.baseline
def test_graph_imports_without_optional_tooling():
    graph_module = importlib.import_module("cortex.graph")

    assert graph_module.graph is not None
    assert isinstance(graph_module.surfer_tools, list)
    assert isinstance(graph_module.operator_tools, list)
