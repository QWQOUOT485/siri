from types import SimpleNamespace

import app.adapters.windows.process as process_module
from app.adapters.windows.process import WindowsProcessController
from app.domain.actions import ValidatedAction
from app.domain.app_models import ProcessSpec


def test_process_resolver_never_closes_without_reliable_identity(fake_runtime, sample_entries):
    runtime, _, process, _, _, _ = fake_runtime
    # The service must fail closed before calling an adapter when process hints
    # are missing; this test never sends WM_CLOSE or touches a real process.
    result = runtime.application_service.close_app(app_query="Installed Only")
    assert result.success is False
    assert result.error_code == "UNSAFE_PROCESS_MAPPING"
    assert process.calls == []


def test_force_close_is_only_selected_by_explicit_service_action(fake_runtime):
    runtime, _, process, _, _, _ = fake_runtime
    graceful = runtime.command_service.execute(ValidatedAction(action="close_app", app_query="Discord"))
    forced = runtime.command_service.execute(ValidatedAction(action="force_close_app", app_query="Discord"))
    assert graceful.success and forced.success
    assert process.calls[-2][1] is False
    assert process.calls[-1][1] is True


def test_force_close_terminates_each_pid_only_once(monkeypatch):
    controller = WindowsProcessController()
    terminated = []

    monkeypatch.setattr("app.adapters.windows.process.sys.platform", "win32")
    monkeypatch.setattr(
        controller,
        "_find_windowed_processes",
        lambda _process: [(123, 1001), (123, 1002), (456, 1003)],
    )
    monkeypatch.setattr(controller, "_terminate", lambda pid: terminated.append(pid) or True)

    result = controller.close(ProcessSpec(executable_names=("app.exe",), reliable=True), force=True)

    assert result.success is True
    assert terminated == [123, 456]
    assert result.data == {"count": 2}


class _FakeKernel32:
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x102
    WAIT_FAILED = 0xFFFFFFFF

    def __init__(self, *, wait_sequences=None, open_fail_for=()):
        self.wait_sequences = {pid: list(sequence) for pid, sequence in (wait_sequences or {}).items()}
        self.open_fail_for = set(open_fail_for)
        self.open_calls = []
        self.wait_calls = []
        self.closed_handles = []
        self.events = []
        self.handles = {}
        self._next_handle = 100

    def OpenProcess(self, access, _inherit, pid):
        self.open_calls.append((access, pid))
        self.events.append(("open", pid))
        if pid in self.open_fail_for:
            return 0
        handle = self._next_handle
        self._next_handle += 1
        self.handles[handle] = pid
        return handle

    def WaitForSingleObject(self, handle, timeout):
        pid = self.handles[handle]
        self.wait_calls.append((handle, pid, timeout))
        self.events.append(("wait", pid))
        sequence = self.wait_sequences[pid]
        return sequence.pop(0) if len(sequence) > 1 else sequence[0]

    def CloseHandle(self, handle):
        self.closed_handles.append(handle)
        self.events.append(("close", handle))
        return 1


def _run_graceful_close_with_wait(
    monkeypatch,
    *,
    targets=((123, 1001),),
    wait_sequences=None,
    open_fail_for=(),
    clock=(0.0, 0.0, 6.0),
):
    controller = WindowsProcessController()
    kernel32 = _FakeKernel32(wait_sequences=wait_sequences, open_fail_for=open_fail_for)
    monkeypatch.setattr(process_module.sys, "platform", "win32")
    monkeypatch.setattr(controller, "_find_windowed_processes", lambda _process: list(targets))

    def post_message(_hwnd, *_args):
        kernel32.events.append(("post", _hwnd))
        return 1

    monkeypatch.setattr(
        process_module.ctypes,
        "windll",
        SimpleNamespace(user32=SimpleNamespace(PostMessageW=post_message), kernel32=kernel32),
        raising=False,
    )
    times = iter(clock)
    monkeypatch.setattr(process_module.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(process_module.time, "sleep", lambda _seconds: None)
    result = controller.close(ProcessSpec(executable_names=("app.exe",), reliable=True))
    return result, kernel32


def test_graceful_close_checks_alive_target_before_sending_wm_close_and_closes_handle(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(
        monkeypatch,
        wait_sequences={123: [_FakeKernel32.WAIT_TIMEOUT, _FakeKernel32.WAIT_OBJECT_0]},
        clock=(0.0, 0.0),
    )
    assert result.success is True
    assert result.error_code is None
    assert kernel32.open_calls == [(WindowsProcessController.SYNCHRONIZE, 123)]
    assert len(kernel32.wait_calls) == 2
    assert kernel32.events.index(("wait", 123)) < kernel32.events.index(("post", 1001))
    assert kernel32.closed_handles == [100]


def test_graceful_close_returns_success_when_process_becomes_signaled(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(
        monkeypatch,
        wait_sequences={123: [_FakeKernel32.WAIT_TIMEOUT, _FakeKernel32.WAIT_OBJECT_0]},
        clock=(0.0, 0.0),
    )
    assert result.success is True
    assert kernel32.closed_handles == [100]


def test_graceful_close_times_out_when_process_remains_alive(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(
        monkeypatch,
        wait_sequences={123: [_FakeKernel32.WAIT_TIMEOUT, _FakeKernel32.WAIT_TIMEOUT]},
    )
    assert result.success is False
    assert result.error_code == "GRACEFUL_CLOSE_TIMEOUT"
    assert result.data == {"remaining": 1}
    assert kernel32.closed_handles == [100]


def test_graceful_close_wait_failure_never_reports_success(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(
        monkeypatch,
        wait_sequences={123: [_FakeKernel32.WAIT_TIMEOUT, _FakeKernel32.WAIT_FAILED]},
        clock=(0.0, 0.0),
    )
    assert result.success is False
    assert result.error_code == "GRACEFUL_CLOSE_INSPECTION_FAILED"
    assert kernel32.closed_handles == [100]


def test_graceful_close_open_failure_never_sends_wm_close_or_reports_success(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(monkeypatch, open_fail_for=(123,))

    assert result.success is False
    assert result.error_code == "GRACEFUL_CLOSE_INSPECTION_FAILED"
    assert kernel32.wait_calls == []
    assert kernel32.closed_handles == []


def test_graceful_close_closes_handles_already_acquired_before_later_open_failure(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(
        monkeypatch,
        targets=((123, 1001), (456, 1002)),
        wait_sequences={123: [_FakeKernel32.WAIT_TIMEOUT]},
        open_fail_for=(456,),
    )

    assert result.success is False
    assert result.error_code == "GRACEFUL_CLOSE_INSPECTION_FAILED"
    assert kernel32.closed_handles == [100]


def test_graceful_close_opens_one_wait_handle_for_multiple_windows_of_one_pid(monkeypatch):
    result, kernel32 = _run_graceful_close_with_wait(
        monkeypatch,
        targets=((123, 1001), (123, 1002)),
        wait_sequences={123: [_FakeKernel32.WAIT_TIMEOUT, _FakeKernel32.WAIT_OBJECT_0]},
        clock=(0.0, 0.0),
    )

    assert result.success is True
    assert kernel32.open_calls == [(WindowsProcessController.SYNCHRONIZE, 123)]
    assert kernel32.closed_handles == [100]
