"""Focused, offline regressions for the first four issue #52 findings."""

import inspect
import asyncio
import threading
from pathlib import PureWindowsPath
from types import SimpleNamespace

import httpx
import pytest

import app.adapters.windows.launcher as launcher_module
import app.adapters.windows.process as process_module
import app.adapters.windows.system_apps as system_apps_module
import app.adapters.windows.system_paths as system_paths_module
from app.adapters.windows.launcher import WindowsLauncher
from app.adapters.windows.process import WindowsProcessController
from app.domain.app_models import LaunchMethod, ProcessSpec
from app.main import create_app
from app.services.spotify_clarification import SpotifyClarificationStore
from tests.unit.test_spotify_clarification import candidate
from tests.unit.test_windows_security_hardening import launch_spec, patch_interactive_windows
from app.api.routes_action import action
from app.api.routes_command import command


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (r"C:\AppB\shared.exe", False),
        (r"C:\AppA\shared.exe", True),
        (r"c:/appa/SHARED.EXE", True),
    ],
)
def test_discovered_process_requires_full_path_identity(actual, expected):
    spec = ProcessSpec(executable_paths=(r"C:\AppA\shared.exe",), reliable=True)
    assert WindowsProcessController._matches_identity(PureWindowsPath(actual), spec) is expected


def test_window_discovery_selects_only_correct_full_path(monkeypatch):
    controller = WindowsProcessController()
    monkeypatch.setattr(process_module.sys, "platform", "win32")
    monkeypatch.setattr(process_module.ctypes, "WINFUNCTYPE", lambda *_args: lambda callback: callback, raising=False)

    class User32:
        def IsWindowVisible(self, _hwnd):
            return True

        def GetWindowThreadProcessId(self, hwnd, pid_ref):
            process_module.ctypes.cast(pid_ref, process_module.ctypes.POINTER(process_module.wintypes.DWORD))[0] = hwnd

        def EnumWindows(self, callback, _data):
            callback(101, 0)
            callback(102, 0)

    monkeypatch.setattr(process_module.ctypes, "windll", SimpleNamespace(user32=User32()), raising=False)
    monkeypatch.setattr(controller, "_current_session_id", lambda: 1)
    monkeypatch.setattr(controller, "_process_session_id", lambda _pid: 1)
    monkeypatch.setattr(controller, "_process_path", lambda pid: PureWindowsPath(r"C:\AppA\shared.exe" if pid == 101 else r"C:\AppB\shared.exe"))
    spec = ProcessSpec(executable_paths=(r"C:\AppA\shared.exe",), reliable=True)
    assert controller._find_windowed_processes(spec) == [(101, 101)]


def test_session_inspection_failure_never_matches(monkeypatch):
    controller = WindowsProcessController()
    monkeypatch.setattr(process_module.sys, "platform", "win32")
    monkeypatch.setattr(controller, "_current_session_id", lambda: -1)
    spec = ProcessSpec(executable_paths=(r"C:\AppA\shared.exe",), reliable=True)
    assert controller._find_windowed_processes(spec) == []
    assert controller._same_session(123) is False


@pytest.mark.parametrize(
    "phrase",
    ["不要第一首", "不是第二首", "第一首不要", "別放第一首", "不要第二個", "不要第一个",
     "不是第一首", "不要第二首", "not the first", "not the second one",
     "don't choose the first", "anything but the first", "不是第一首，選第二首"],
)
def test_negative_ordinal_does_not_select_or_consume_token(phrase):
    store = SpotifyClarificationStore()
    token = store.create([candidate("one", "Artist One", "A"), candidate("two", "Artist Two", "B")])
    rejected = store.select(token, phrase)
    assert rejected.track is None
    assert rejected.error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"
    assert rejected.clarification_token == token
    assert store.select(token, "第一首").track.track_id == "one"


@pytest.mark.parametrize("phrase,index", [
    ("第一首", 0), ("第一個", 0), ("第一个", 0), ("選第一首", 0),
    ("就第一首", 0), ("我要第一首", 0), ("first", 0),
    ("the first", 0), ("choose the first", 0), ("第二首", 1),
    ("第三首", 2), ("the third one", 2),
])
def test_closed_positive_ordinal_forms(phrase, index):
    store = SpotifyClarificationStore()
    token = store.create([candidate(str(i), f"Artist {i}", f"Album {i}") for i in range(3)])
    assert store.select(token, phrase).track.track_id == str(index)
    assert store.select(token, phrase).error_code == "SPOTIFY_CLARIFICATION_USED"


@pytest.mark.parametrize("phrase", ["第三首", "the third", "選第三首", "not Artist One", "不要 Artist One"])
def test_out_of_bounds_or_negative_label_remains_unclear(phrase):
    store = SpotifyClarificationStore()
    token = store.create([candidate("one", "Artist One", "Album One"), candidate("two", "Artist Two", "Album Two")])
    assert store.select(token, phrase).error_code == "SPOTIFY_CLARIFICATION_UNCLEAR"


def test_blocking_routes_are_sync_endpoints():
    assert not inspect.iscoroutinefunction(action)
    assert not inspect.iscoroutinefunction(command)


@pytest.mark.parametrize("route,body", [("/action", {"action": "open_app", "app_name": "Discord"}), ("/command", {"text": "開啟 Discord"})])
def test_slow_command_does_not_block_health(fake_runtime, route, body):
    runtime = fake_runtime[0]
    entered, release = threading.Event(), threading.Event()
    original = runtime.command_service.execute

    def slow_execute(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)

    runtime.command_service.execute = slow_execute
    app = create_app(runtime, refresh_on_startup=False, test_mode=True)
    async def probe():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            pending = asyncio.create_task(client.post(route, headers={"X-API-Key": "test-key"}, json=body))
            try:
                assert await asyncio.to_thread(entered.wait, 2)
                health = await asyncio.wait_for(client.get("/health"), 1)
                assert health.status_code == 200
            finally:
                release.set()
                response = await pending
            assert response.status_code == 200

    asyncio.run(probe())


@pytest.mark.parametrize("target", [
    "devmgmt.msc", r"C:\temp\devmgmt.msc", r"\\server\share\devmgmt.msc",
    r"\\?\C:\Windows\System32\devmgmt.msc", r"\\.\C:\Windows\System32\devmgmt.msc",
    r"C:\Windows\System32\..\System32\devmgmt.msc", r"C:\Windows\System32\evil.msc",
])
def test_msc_launcher_rejects_non_system_identity(monkeypatch, target):
    patch_interactive_windows(monkeypatch)
    trusted = r"C:\Windows\System32\devmgmt.msc"
    started = []
    monkeypatch.setattr(launcher_module, "trusted_msc_path", lambda name: trusted if name == "devmgmt.msc" else None)
    monkeypatch.setattr(launcher_module.Path, "is_file", lambda self: True)
    monkeypatch.setattr(launcher_module.Path, "resolve", lambda self, strict=False: self)
    monkeypatch.setattr(launcher_module.os, "startfile", started.append, raising=False)
    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_EXECUTE, target))
    assert result.error_code == "INVALID_SYSTEM_TARGET"
    assert started == []


def test_msc_launcher_rejects_file_resolving_outside_system32(monkeypatch):
    patch_interactive_windows(monkeypatch)
    trusted = r"C:\Windows\System32\devmgmt.msc"
    started = []
    monkeypatch.setattr(launcher_module, "trusted_msc_path", lambda _name: trusted)
    monkeypatch.setattr(launcher_module.Path, "is_file", lambda self: True)
    monkeypatch.setattr(launcher_module.Path, "resolve", lambda self, strict=False: PureWindowsPath(r"C:\temp\devmgmt.msc"))
    monkeypatch.setattr(launcher_module.os, "startfile", started.append, raising=False)
    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_EXECUTE, trusted))
    assert result.error_code == "INVALID_SYSTEM_TARGET"
    assert started == []


def test_msc_system_directory_comes_from_windows_api_and_id_stays_stable(monkeypatch):
    monkeypatch.setattr(system_paths_module.sys, "platform", "win32")

    def get_system_directory(buffer, _length):
        buffer.value = r"C:\Windows\System32"
        return len(buffer.value)

    monkeypatch.setattr(system_paths_module.ctypes, "windll", SimpleNamespace(kernel32=SimpleNamespace(GetSystemDirectoryW=get_system_directory)), raising=False)
    target = system_paths_module.trusted_msc_path("devmgmt.msc")
    assert target == r"C:\Windows\System32\devmgmt.msc"
    entries = system_apps_module.system_app_entries()
    device = next(entry for entry in entries if entry.display_name == "Device Manager")
    assert device.launch_target == target
    assert device.app_id == system_apps_module.stable_app_id("system_apps", "Device Manager", "devmgmt.msc")


@pytest.mark.parametrize("image_path,expected", [
    (r"C:\AppB\shared.exe", False), (r"C:\AppA\shared.exe", True),
])
def test_force_close_rechecks_image_on_termination_handle(monkeypatch, image_path, expected):
    controller = WindowsProcessController()
    monkeypatch.setattr(controller, "_current_session_id", lambda: 1)
    monkeypatch.setattr(controller, "_process_session_id", lambda _pid: 1)
    terminated = []

    class Kernel:
        def OpenProcess(self, _access, _inherit, _pid):
            return 42

        def QueryFullProcessImageNameW(self, _handle, _flags, buffer, _size):
            buffer.value = image_path
            return 1

        def TerminateProcess(self, handle, _code):
            terminated.append(handle)
            return 1

        def CloseHandle(self, _handle):
            return 1

    monkeypatch.setattr(process_module.ctypes, "windll", SimpleNamespace(kernel32=Kernel()), raising=False)
    assert controller._terminate(123, ProcessSpec(executable_paths=(r"C:\AppA\shared.exe",), reliable=True)) is expected
    assert terminated == ([42] if expected else [])


def test_public_app_view_does_not_serialize_process_path(tmp_path):
    from app.adapters.windows.discovery import _path_entry

    target = tmp_path / "shared.exe"
    entry = _path_entry(display_name="Shared", target=target, source="manual_apps")
    assert entry.process.executable_paths
    assert str(target) not in repr(entry.public_view())
