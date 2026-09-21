from __future__ import annotations

from pathlib import Path

import pytest

import app.adapters.windows.launcher as launcher_module
import app.adapters.windows.media as media_module
import app.adapters.windows.system as system_module
import app.adapters.windows.volume as volume_module
from app.adapters.windows.base import OperationResult
from app.adapters.windows.launcher import WindowsLauncher, WindowsWebsiteOpener
from app.adapters.windows.system import WindowsSystemController
from app.adapters.windows.system_apps import system_app_entries
from app.catalog import ApplicationCatalog
from app.domain.app_models import AppType, DiscoveryDiagnostics, LaunchMethod, LaunchSource, LaunchSpec
from app.services.app_service import ApplicationService, WebsiteCatalog


def launch_spec(
    method: LaunchMethod,
    target: str,
    *,
    source: LaunchSource = LaunchSource.TRUSTED,
    verified: bool = True,
    executable_path: str | None = None,
    arguments: tuple[str, ...] = (),
    working_directory: str | None = None,
) -> LaunchSpec:
    return LaunchSpec(
        app_id="app_launcher_test",
        method=method,
        target=target,
        arguments=arguments,
        working_directory=working_directory,
        launch_source=source,
        verified=verified,
        executable_path=executable_path,
    )


def patch_interactive_windows(monkeypatch, *, interactive: bool = True) -> None:
    monkeypatch.setattr(launcher_module.sys, "platform", "win32")
    monkeypatch.setattr(media_module.sys, "platform", "win32")
    monkeypatch.setattr(system_module.sys, "platform", "win32")
    monkeypatch.setattr(volume_module.sys, "platform", "win32")
    monkeypatch.setattr(
        WindowsSystemController,
        "session_info",
        lambda self: {"interactive": interactive, "session_id": 1},
    )


def test_windows_launcher_rejects_unverified_launch_spec():
    result = WindowsLauncher().launch(
        launch_spec(LaunchMethod.SHELL_URI, "ms-settings:", verified=False)
    )

    assert result.success is False
    assert result.error_code == "UNVERIFIED_LAUNCH"


def test_windows_launcher_rejects_untrusted_launch_source():
    result = WindowsLauncher().launch(
        launch_spec(LaunchMethod.SHELL_URI, "ms-settings:", source=LaunchSource.METADATA_ONLY)
    )

    assert result.success is False
    assert result.error_code == "UNTRUSTED_LAUNCH_SOURCE"


def test_windows_launcher_rejects_non_interactive_session(monkeypatch):
    patch_interactive_windows(monkeypatch, interactive=False)

    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_URI, "ms-settings:"))

    assert result.success is False
    assert result.error_code == "NON_INTERACTIVE_SESSION"


def test_windows_launcher_rejects_invalid_shell_uri(monkeypatch):
    patch_interactive_windows(monkeypatch)
    started = []
    monkeypatch.setattr(launcher_module.os, "startfile", started.append, raising=False)

    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_URI, "https://untrusted.example"))

    assert result.success is False
    assert result.error_code == "INVALID_SHELL_TARGET"
    assert started == []


def test_windows_launcher_accepts_approved_shell_uri_through_startfile(monkeypatch):
    patch_interactive_windows(monkeypatch)
    started = []
    monkeypatch.setattr(launcher_module.os, "startfile", started.append, raising=False)

    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_URI, "ms-settings:"))

    assert result.success is True
    assert started == ["ms-settings:"]


def test_windows_launcher_rejects_unapproved_msc(monkeypatch):
    patch_interactive_windows(monkeypatch)
    started = []
    monkeypatch.setattr(launcher_module.os, "startfile", started.append, raising=False)

    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_EXECUTE, "evil.msc"))

    assert result.success is False
    assert result.error_code == "INVALID_SYSTEM_TARGET"
    assert started == []


def test_windows_launcher_allows_approved_msc(monkeypatch):
    patch_interactive_windows(monkeypatch)
    started = []
    monkeypatch.setattr(launcher_module.os, "startfile", started.append, raising=False)

    result = WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_EXECUTE, "devmgmt.msc"))

    assert result.success is True
    assert started == ["devmgmt.msc"]


def test_windows_launcher_enforces_executable_extension_gate(monkeypatch, tmp_path):
    patch_interactive_windows(monkeypatch)
    target = tmp_path / "not-an-executable.txt"
    target.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(launcher_module.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("must not start"))

    result = WindowsLauncher().launch(launch_spec(LaunchMethod.EXECUTABLE, str(target)))

    assert result.success is False
    assert result.error_code == "LAUNCH_TARGET_MISSING"


def test_windows_launcher_rejects_executable_identity_mismatch(monkeypatch, tmp_path):
    patch_interactive_windows(monkeypatch)
    target = tmp_path / "target.exe"
    other = tmp_path / "other.exe"
    target.write_text("target", encoding="utf-8")
    other.write_text("other", encoding="utf-8")

    result = WindowsLauncher().launch(
        launch_spec(
            LaunchMethod.EXECUTABLE,
            str(target),
            executable_path=str(other),
        )
    )

    assert result.success is False
    assert result.error_code == "LAUNCH_IDENTITY_CHANGED"


def test_windows_launcher_uses_list_argv_and_shell_false(monkeypatch, tmp_path):
    patch_interactive_windows(monkeypatch)
    target = tmp_path / "approved.exe"
    target.write_text("fixture", encoding="utf-8")
    calls = []

    def fake_popen(*args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(launcher_module.subprocess, "Popen", fake_popen)
    result = WindowsLauncher().launch(
        launch_spec(
            LaunchMethod.EXECUTABLE,
            str(target),
            executable_path=str(target),
            arguments=("--safe", "value"),
            working_directory=str(tmp_path),
        )
    )

    assert result.success is True
    assert calls == [
        (
            ([str(target), "--safe", "value"],),
            {"cwd": str(tmp_path), "shell": False, "close_fds": True},
        )
    ]


def test_windows_website_opener_rejects_non_https(monkeypatch):
    monkeypatch.setattr(launcher_module.sys, "platform", "win32")

    result = WindowsWebsiteOpener().open("http://localhost:1234")

    assert result.success is False
    assert result.error_code == "INVALID_WEBSITE"


def test_system_app_close_authority_never_reaches_process_controller(tmp_path):
    entries = system_app_entries()

    class Discovery:
        def discover(self):
            return entries, DiscoveryDiagnostics(scanned_sources=["system"], source_counts={"system": len(entries)})

    class RecordingProcessController:
        def __init__(self):
            self.calls = []

        def close(self, process, *, force=False):
            self.calls.append((process, force))
            return OperationResult(True, "closed")

    process_controller = RecordingProcessController()
    catalog = ApplicationCatalog(Discovery(), tmp_path / "apps.json")
    catalog.refresh()
    service = ApplicationService(
        catalog,
        launcher=object(),
        process_controller=process_controller,
        website_opener=object(),
        website_catalog=WebsiteCatalog(()),
    )

    for query in ("File Explorer", "Command Prompt", "PowerShell"):
        for force in (False, True):
            result = service.close_app(app_query=query, force=force)
            assert result.success is False
            assert result.error_code == "SYSTEM_APP_CLOSE_UNSUPPORTED"

    assert process_controller.calls == []


@pytest.mark.parametrize(
    ("adapter_name", "error_code", "invoke"),
    (
        (
            "launcher",
            "LAUNCH_FAILED",
            lambda monkeypatch: WindowsLauncher().launch(launch_spec(LaunchMethod.SHELL_URI, "ms-settings:")),
        ),
        (
            "website",
            "WEBSITE_OPEN_FAILED",
            lambda monkeypatch: WindowsWebsiteOpener().open("https://example.com"),
        ),
    ),
)
def test_launcher_and_website_errors_do_not_expose_os_details(monkeypatch, adapter_name, error_code, invoke):
    patch_interactive_windows(monkeypatch)
    raw_detail = r"C:\Users\tester\secret\private-file.txt: access denied"

    def fail_startfile(_target):
        raise OSError(raw_detail)

    monkeypatch.setattr(launcher_module.os, "startfile", fail_startfile, raising=False)
    result = invoke(monkeypatch)

    assert result.success is False
    assert result.error_code == error_code
    assert result.data == {}
    assert raw_detail not in repr(result)


def test_media_error_does_not_expose_os_details(monkeypatch):
    patch_interactive_windows(monkeypatch)
    raw_detail = r"C:\Users\tester\secret\media-device.dll"

    def fail_send(_key):
        raise OSError(raw_detail)

    controller = media_module.WindowsMediaController()
    monkeypatch.setattr(controller, "_send_key", fail_send)
    result = controller.send("play_pause")

    assert result.error_code == "MEDIA_CONTROL_FAILED"
    assert result.data == {}
    assert raw_detail not in repr(result)


def test_shutdown_error_does_not_expose_os_details(monkeypatch):
    patch_interactive_windows(monkeypatch)
    raw_detail = r"C:\Users\tester\secret\shutdown.exe"

    def fail_popen(*_args, **_kwargs):
        raise OSError(raw_detail)

    monkeypatch.setattr(system_module.subprocess, "Popen", fail_popen)
    result = WindowsSystemController().shutdown()

    assert result.error_code == "SHUTDOWN_FAILED"
    assert result.data == {}
    assert raw_detail not in repr(result)


def test_volume_errors_do_not_expose_os_details(monkeypatch):
    patch_interactive_windows(monkeypatch)
    raw_detail = r"C:\Users\tester\secret\audio-endpoint.dll"
    controller = volume_module.WindowsVolumeController()
    monkeypatch.setattr(controller, "_endpoint", lambda: None)

    def fail_send(_key):
        raise OSError(raw_detail)

    monkeypatch.setattr(controller._media, "_send_key", fail_send)
    fallback_result = controller.change("volume_up")
    assert fallback_result.error_code == "VOLUME_CONTROL_FAILED"
    assert fallback_result.data == {}
    assert raw_detail not in repr(fallback_result)

    monkeypatch.setattr(controller, "_endpoint", lambda: (_ for _ in ()).throw(OSError(raw_detail)))
    unavailable_result = controller.set_volume(50)
    assert unavailable_result.error_code == "EXACT_VOLUME_UNAVAILABLE"
    assert unavailable_result.data == {}
    assert raw_detail not in repr(unavailable_result)
