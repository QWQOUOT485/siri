from pathlib import Path

from app.domain.app_models import WebsiteEntry
from app.infrastructure.config import load_config
from app.services.app_service import WebsiteCatalog


def test_local_application_alias_config_is_loaded(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app_aliases.yaml").write_text("application_aliases:\n  google chrome: [瀏覽器]\n", encoding="utf-8")
    (config_dir / "websites.yaml").write_text("websites: []\n", encoding="utf-8")
    (config_dir / "manual_apps.yaml").write_text("manual_apps: []\n", encoding="utf-8")
    (config_dir / "allowed_networks.yaml").write_text("allowed_networks: [127.0.0.0/8]\n", encoding="utf-8")
    config = load_config(root_dir=tmp_path, environ={})
    assert config.application_aliases["google chrome"] == ("瀏覽器",)


def test_spotify_configuration_is_local_and_defaults_to_runtime_token_path(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for name, content in {
        "websites.yaml": "websites: []\n",
        "manual_apps.yaml": "manual_apps: []\n",
        "allowed_networks.yaml": "allowed_networks: [127.0.0.0/8]\n",
    }.items():
        (config_dir / name).write_text(content, encoding="utf-8")

    config = load_config(root_dir=tmp_path, environ={"SPOTIFY_CLIENT_ID": "client-id"})

    assert config.spotify_client_id == "client-id"
    assert config.spotify_token_file == (tmp_path / "runtime" / "spotify_token.json").resolve()


def test_website_catalog_never_returns_an_unlisted_url():
    catalog = WebsiteCatalog((WebsiteEntry(website_id="github", display_name="GitHub", aliases=("github",), url="https://github.com/"),))
    assert catalog.find(query="github").entry is not None
    assert catalog.find(query="https://evil.example").entry is None


def test_local_ai_is_off_by_default_and_shadow_is_explicit(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config = load_config(root_dir=tmp_path, environ={})
    assert config.local_ai_enabled is False
    assert config.local_ai_mode == "off"

    shadow = load_config(
        root_dir=tmp_path,
        environ={
            "LOCAL_AI_ENABLED": "true",
            "LOCAL_AI_MODE": "shadow",
            "LOCAL_AI_BASE_URL": "http://127.0.0.1:1234/v1",
            "LOCAL_AI_MODEL": "test-model",
        },
    )
    assert shadow.local_ai_enabled is True
    assert shadow.local_ai_mode == "shadow"
    assert shadow.local_ai_fallback_approved is False


def test_local_ai_enabled_without_explicit_mode_fails_closed_to_off(tmp_path: Path):
    config = load_config(
        root_dir=tmp_path,
        environ={
            "LOCAL_AI_ENABLED": "true",
            "LOCAL_AI_BASE_URL": "http://127.0.0.1:1234/v1",
            "LOCAL_AI_MODEL": "test-model",
        },
    )

    assert config.local_ai_enabled is True
    assert config.local_ai_mode == "off"
