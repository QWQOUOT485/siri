from types import SimpleNamespace

from app.adapters.windows.volume import WindowsVolumeController


def test_volume_key_fallback_honors_bounded_steps(monkeypatch):
    controller = WindowsVolumeController()
    sent = []

    monkeypatch.setattr("app.adapters.windows.volume.sys.platform", "win32")
    monkeypatch.setattr(
        "app.adapters.windows.system.WindowsSystemController.session_info",
        lambda _self: {"interactive": True},
    )
    monkeypatch.setattr(controller, "_endpoint", lambda: None)
    monkeypatch.setattr(controller._media, "_send_key", lambda key: sent.append(key))

    result = controller.change("volume_up", steps=3)

    assert result.success is True
    assert len(sent) == 3
    assert sent == [0xAF, 0xAF, 0xAF]


def test_exact_volume_uses_scalar_setter_without_media_key_or_mute(monkeypatch):
    controller = WindowsVolumeController()
    sent = []
    calls = []

    class Endpoint:
        def SetMasterVolumeLevelScalar(self, value, context):
            calls.append(("scalar", value, context))

        def SetMute(self, value, context):
            calls.append(("mute", value, context))

    monkeypatch.setattr("app.adapters.windows.volume.sys.platform", "win32")
    monkeypatch.setattr(
        "app.adapters.windows.system.WindowsSystemController.session_info",
        lambda _self: {"interactive": True},
    )
    monkeypatch.setattr(controller, "_endpoint", lambda: Endpoint())
    monkeypatch.setattr(controller._media, "_send_key", lambda key: sent.append(key))

    result = controller.set_volume(37)

    assert result.success is True
    assert result.data == {"level": 0.37, "volume_percent": 37}
    assert calls == [("scalar", 0.37, None)]
    assert sent == []


def test_exact_volume_failure_never_approximates_with_media_keys(monkeypatch):
    controller = WindowsVolumeController()
    sent = []

    monkeypatch.setattr("app.adapters.windows.volume.sys.platform", "win32")
    monkeypatch.setattr(
        "app.adapters.windows.system.WindowsSystemController.session_info",
        lambda _self: {"interactive": True},
    )
    monkeypatch.setattr(controller, "_endpoint", lambda: None)
    monkeypatch.setattr(controller._media, "_send_key", lambda key: sent.append(key))

    result = controller.set_volume(37)

    assert result.success is False
    assert result.error_code == "EXACT_VOLUME_UNAVAILABLE"
    assert sent == []
