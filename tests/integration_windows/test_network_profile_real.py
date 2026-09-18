import sys

import pytest

from app.adapters.windows.firewall import WindowsFirewallInspector


pytestmark = [
    pytest.mark.windows_integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows integration tests require a real Windows host"),
]


def test_network_and_firewall_inspection_is_read_only():
    inspector = WindowsFirewallInspector()
    profile = inspector.inspect_network_profile()
    rule = inspector.inspect_firewall_rule()
    assert isinstance(profile, dict)
    assert isinstance(rule, dict)
    assert "profiles" in profile or "warning" in profile
    assert "exists" in rule
