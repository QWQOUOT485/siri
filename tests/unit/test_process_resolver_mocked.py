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


def test_pid_liveness_requests_query_and_synchronize_rights(monkeypatch):
    class FakeKernel32:
        def __init__(self):
            self.access = None

        def OpenProcess(self, access, _inherit, _pid):
            self.access = access
            return 100

        @staticmethod
        def GetExitCodeProcess(_handle, output):
            output._obj.value = 259
            return 1

        @staticmethod
        def CloseHandle(_handle):
            return 1

    kernel32 = FakeKernel32()
    monkeypatch.setattr(process_module.ctypes, "windll", SimpleNamespace(kernel32=kernel32), raising=False)

    assert WindowsProcessController._pid_exists(123) is True
    assert kernel32.access == WindowsProcessController.SYNCHRONIZE | WindowsProcessController.PROCESS_QUERY_LIMITED_INFORMATION


def test_pid_liveness_removes_a_confirmed_exited_pid(monkeypatch):
    class FakeKernel32:
        @staticmethod
        def OpenProcess(_access, _inherit, _pid):
            return 100

        @staticmethod
        def GetExitCodeProcess(_handle, output):
            output._obj.value = 0
            return 1

        @staticmethod
        def CloseHandle(_handle):
            return 1

    monkeypatch.setattr(process_module.ctypes, "windll", SimpleNamespace(kernel32=FakeKernel32()), raising=False)
    assert WindowsProcessController._pid_exists(123) is False


def _run_graceful_close_with_liveness(monkeypatch, liveness):
    controller = WindowsProcessController()
    monkeypatch.setattr(process_module.sys, "platform", "win32")
    monkeypatch.setattr(controller, "_find_windowed_processes", lambda _process: [(123, 1001)])
    monkeypatch.setattr(
        process_module.ctypes,
        "windll",
        SimpleNamespace(user32=SimpleNamespace(PostMessageW=lambda *_args: 1)),
        raising=False,
    )
    clock = iter((0.0, 0.0, 6.0))
    monkeypatch.setattr(process_module.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(process_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(controller, "_pid_exists", lambda _pid: liveness)
    return controller.close(ProcessSpec(executable_names=("app.exe",), reliable=True))


def test_graceful_close_removes_exited_pid(monkeypatch):
    result = _run_graceful_close_with_liveness(monkeypatch, False)
    assert result.success is True
    assert result.error_code is None


def test_graceful_close_keeps_live_pid_and_returns_timeout(monkeypatch):
    result = _run_graceful_close_with_liveness(monkeypatch, True)
    assert result.success is False
    assert result.error_code == "GRACEFUL_CLOSE_TIMEOUT"
    assert result.data == {"remaining": 1}


def test_graceful_close_inspection_failure_is_not_false_success(monkeypatch):
    result = _run_graceful_close_with_liveness(monkeypatch, None)
    assert result.success is False
    assert result.error_code == "GRACEFUL_CLOSE_TIMEOUT"
