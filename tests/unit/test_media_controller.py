from __future__ import annotations

import ctypes
from types import SimpleNamespace

from app.adapters.windows.media import WindowsMediaController


class PointerCheckingUser32:
    def __init__(self) -> None:
        self.calls: list[tuple[int, object, int]] = []

    def SendInput(self, count: int, inputs: object, size: int) -> int:
        self.calls.append((count, inputs, size))
        if not hasattr(inputs, "_obj"):
            raise TypeError("SendInput expects a pointer to an INPUT array")
        return count


def test_send_input_receives_a_pointer_to_the_input_array(monkeypatch):
    user32 = PointerCheckingUser32()
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)

    WindowsMediaController._send_key(0xB3)

    assert len(user32.calls) == 1
    assert user32.calls[0][0] == 2
