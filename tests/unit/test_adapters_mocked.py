from app.adapters.windows.base import OperationResult
from app.catalog import ApplicationCatalog
from app.domain.app_models import LaunchSource


def test_catalog_builds_verified_launch_spec_only_for_trusted_entry(tmp_path, sample_entries):
    from tests.unit.conftest import FakeDiscovery

    catalog = ApplicationCatalog(FakeDiscovery(sample_entries), tmp_path / "apps.json")
    catalog.refresh()
    trusted = catalog.get("app_discord_12345678")
    metadata = catalog.get("app_installed_only_12345678")
    assert trusted is not None and catalog.launch_spec(trusted) is not None
    assert catalog.launch_spec(metadata) is None


def test_process_service_receives_force_flag(fake_runtime):
    runtime, _, process, _, _, _ = fake_runtime
    assert runtime.application_service.close_app(app_query="Discord", force=False).success
    assert process.calls[-1][1] is False
    assert runtime.application_service.close_app(app_query="Discord", force=True).success
    assert process.calls[-1][1] is True
