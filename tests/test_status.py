"""Observed resource status round trips and window isolation."""
from dataclasses import asdict

import pytest

from Imervue.plugin.status import PluginStatus, StatusRegistry, STATES


@pytest.mark.parametrize("state", sorted(STATES))
def test_publish_round_trip_and_scope(state):
    registry = StatusRegistry()
    registry.publish("shared", "Resource", state, "model/backend reason")
    registry.publish("window-one", "Plugin", state, scope="one")
    registry.publish("window-two", "Plugin", state, scope="two")
    rows = registry.snapshot("one")
    assert {row.key for row in rows} == {"shared", "window-one"}
    assert PluginStatus(**asdict(rows[0])) == rows[0]
    registry.clear("one")
    assert {row.key for row in registry.snapshot()} == {"shared", "window-two"}
    registry.publish("shared", "Resource", "available")
    assert registry.snapshot("one")[0].status == "available"


def test_invalid_and_empty():
    registry = StatusRegistry()
    assert registry.snapshot() == ()
    with pytest.raises(ValueError):
        registry.publish("key", "name", "imaginary")
