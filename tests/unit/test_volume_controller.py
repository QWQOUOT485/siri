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
