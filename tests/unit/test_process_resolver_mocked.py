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
