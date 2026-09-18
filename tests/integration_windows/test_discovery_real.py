import sys

import pytest

from app.adapters.windows.discovery import WindowsApplicationDiscovery


pytestmark = [
    pytest.mark.windows_integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows integration tests require a real Windows host"),
]


def test_real_discovery_finds_fixed_windows_tools_without_drive_scan():
    entries, diagnostics = WindowsApplicationDiscovery().discover()
    names = {entry.display_name for entry in entries}
    assert "Notepad" in names
    assert "Task Manager" in names
    assert "File Explorer" in names
    assert "system_apps" in diagnostics.scanned_sources
    assert "C:\\" not in diagnostics.scanned_sources


def test_shortcut_and_apps_folder_sources_are_read_only():
    _, diagnostics = WindowsApplicationDiscovery().discover()
    assert "start_menu_shortcuts" in diagnostics.scanned_sources
    assert "apps_folder" in diagnostics.scanned_sources
