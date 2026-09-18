import sys

import pytest

from app.adapters.windows.discovery import WindowsApplicationDiscovery


pytestmark = [
    pytest.mark.windows_integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows integration tests require a real Windows host"),
]


def test_registry_app_paths_discovery_does_not_crash():
    entries, diagnostics = WindowsApplicationDiscovery().discover()
    assert "registry_app_paths" in diagnostics.scanned_sources
    assert all(entry.launch_source.value in {"trusted", "metadata_only", "manual"} for entry in entries)
