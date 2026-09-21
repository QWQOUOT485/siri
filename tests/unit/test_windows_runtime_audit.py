from __future__ import annotations

from ctypes import wintypes
from types import SimpleNamespace

import app.adapters.windows.system as system_module
from app.adapters.windows.discovery import WindowsApplicationDiscovery
from app.domain.app_models import AppEntry, AppType, LaunchMethod, LaunchSource, ProcessSpec
from app.infrastructure.network import ip_allowed, parse_networks


def _trusted_app(app_id: str, *, target: str, source: str = "start_menu_shortcuts") -> AppEntry:
    return AppEntry(
        app_id=app_id,
        display_name="网易云音乐",
        normalized_name="網易雲音樂",
        aliases=("網易雲音樂",),
        launch_method=LaunchMethod.EXECUTABLE,
        launch_target=target,
        executable_path=target,
        process=ProcessSpec(executable_names=("cloudmusic.exe",), reliable=True),
        source=source,
        app_type=AppType.DESKTOP,
        launch_source=LaunchSource.TRUSTED,
        launch_confidence=0.9,
        metadata_confidence=0.9,
        metadata={"arguments": []},
    )


def _metadata_app(app_id: str) -> AppEntry:
    return AppEntry(
        app_id=app_id,
        display_name="網易雲音樂",
        normalized_name="網易雲音樂",
        aliases=(),
        source="registry_uninstall",
        app_type=AppType.METADATA,
        launch_source=LaunchSource.METADATA_ONLY,
        metadata_confidence=0.8,
        metadata={"publisher": "Vendor", "version": "1.2.3"},
    )


def test_discovery_metadata_merge_replaces_trusted_row_without_duplicate_app_id():
    trusted = _trusted_app("app_netease_12345678", target="C:\\Apps\\cloudmusic.exe")
    metadata = _metadata_app("app_metadata_12345678")

    result = WindowsApplicationDiscovery._deduplicate([trusted, metadata])

    assert [entry.app_id for entry in result] == [trusted.app_id]
    assert result[0].launch_source is LaunchSource.TRUSTED
    assert result[0].launch_target == trusted.launch_target
    assert result[0].process == trusted.process
    assert result[0].metadata["publisher"] == "Vendor"


def test_discovery_metadata_merge_is_order_independent():
    trusted = _trusted_app("app_netease_12345678", target="C:\\Apps\\cloudmusic.exe")
    metadata = _metadata_app("app_metadata_12345678")

    result = WindowsApplicationDiscovery._deduplicate([metadata, trusted])

    assert [entry.app_id for entry in result] == [trusted.app_id]
    assert result[0].metadata["version"] == "1.2.3"


def test_discovery_keeps_metadata_when_same_name_has_multiple_trusted_targets():
    first = _trusted_app("app_netease_one_12345678", target="C:\\Apps\\one.exe")
    second = _trusted_app("app_netease_two_12345678", target="C:\\Apps\\two.exe")
    metadata = _metadata_app("app_metadata_12345678")

    result = WindowsApplicationDiscovery._deduplicate([first, second, metadata])

    assert {entry.app_id for entry in result} == {first.app_id, second.app_id, metadata.app_id}
    assert all(entry.app_id != first.app_id or "publisher" not in entry.metadata for entry in result)


class _FakeFunction:
    def __init__(self, result):
        self.result = result
        self.restype = None

    def __call__(self):
        return self.result


def _session_kernel(session_id: int, active_session: int):
    active = _FakeFunction(active_session)

    def process_id_to_session(_pid, output):
        output._obj.value = session_id
        return 1

    return SimpleNamespace(ProcessIdToSessionId=process_id_to_session, WTSGetActiveConsoleSessionId=active)


def _session_info(monkeypatch, *, user: str, session_id: int, active_session: int):
    monkeypatch.setattr(system_module.sys, "platform", "win32")
    monkeypatch.setattr(system_module.getpass, "getuser", lambda: user)
    monkeypatch.setattr(system_module.os, "getpid", lambda: 777)
    kernel32 = _session_kernel(session_id, active_session)
    monkeypatch.setattr(system_module.ctypes, "windll", SimpleNamespace(kernel32=kernel32), raising=False)
    return system_module.WindowsSystemController().session_info(), kernel32


def test_active_console_session_uses_dword_restype(monkeypatch):
    info, kernel32 = _session_info(monkeypatch, user="tester", session_id=3, active_session=3)
    assert info["interactive"] is True
    assert kernel32.WTSGetActiveConsoleSessionId.restype is wintypes.DWORD


def test_active_console_session_dword_sentinel_remains_interactive(monkeypatch):
    info, _ = _session_info(monkeypatch, user="tester", session_id=3, active_session=0xFFFFFFFF)
    assert info["interactive"] is True


def test_system_user_is_not_interactive_even_with_matching_session(monkeypatch):
    info, _ = _session_info(monkeypatch, user="SYSTEM", session_id=3, active_session=3)
    assert info["interactive"] is False


def test_mismatched_active_session_is_not_interactive(monkeypatch):
    info, _ = _session_info(monkeypatch, user="tester", session_id=3, active_session=4)
    assert info["interactive"] is False


def test_ip_allowlist_accepts_ipv4_and_ipv4_mapped_ipv6():
    networks = parse_networks(("192.168.0.0/16",))
    assert ip_allowed("192.168.1.100", networks) is True
    assert ip_allowed("::ffff:192.168.1.100", networks) is True
    assert ip_allowed("::ffff:8.8.8.8", networks) is False


def test_ip_allowlist_preserves_ipv6_and_rejects_invalid_or_empty_addresses():
    networks = parse_networks(("fd00::/8",))
    assert ip_allowed("fd00::1234", networks) is True
    assert ip_allowed("not-an-ip", networks) is False
    assert ip_allowed("", networks) is False
    assert ip_allowed(None, networks) is False
