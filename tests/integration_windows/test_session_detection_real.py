import getpass
import sys

import pytest

from app.adapters.windows.system import WindowsSystemController


pytestmark = [
    pytest.mark.windows_integration,
    pytest.mark.skipif(sys.platform != "win32", reason="Windows integration tests require a real Windows host"),
]


def test_current_process_session_is_reported_without_touching_desktop():
    info = WindowsSystemController().session_info()
    assert info["user"] == getpass.getuser()
    assert "interactive" in info
    assert "warning" in info
