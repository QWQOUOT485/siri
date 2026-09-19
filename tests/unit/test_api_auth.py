from fastapi.testclient import TestClient

from app.adapters.windows.base import OperationResult
from app.main import create_app


def test_health_is_public_but_control_routes_require_key(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    assert client.get("/health").status_code == 200
    assert client.get("/apps").status_code == 401
    assert client.get("/apps", headers={"X-API-Key": "wrong"}).status_code == 401
    response = client.get("/apps", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["apps"]
    assert all("launch_target" not in item for item in response.json()["apps"])


def test_command_executes_only_after_catalog_resolution(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    response = client.post("/command", headers={"X-API-Key": "test-key"}, json={"text": "開啟 Discord"})
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert launcher.specs[0].app_id.startswith("app_discord")
    assert not hasattr(launcher.specs[0], "command")


def test_play_command_uses_spotify_and_never_falls_back_to_system_media_keys(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    response = client.post("/command", headers={"X-API-Key": "test-key"}, json={"text": "播放"})

    assert response.status_code == 200
    assert response.json()["action"] == "spotify_resume"
    assert response.json()["error_code"] == "SPOTIFY_AUTH_REQUIRED"
    assert media.actions == []


def test_action_exact_volume_is_wired_to_windows_volume_service(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post(
        "/action",
        headers={"X-API-Key": "test-key"},
        json={"action": "set_volume", "volume_percent": 37},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["action"] == "set_volume"
    assert response.json()["data"]["level"] == 0.37
    assert volume.exact_calls == [37]


def test_spotify_status_and_auth_start_never_return_a_token(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    headers = {"X-API-Key": "test-key"}

    status = client.get("/spotify/status", headers=headers)
    start = client.get("/spotify/auth/start", headers=headers)

    assert status.status_code == 200
    assert status.json()["data"] == {"authorized": False}
    assert "access_token" not in status.text
    assert "refresh_token" not in status.text
    assert start.json()["error_code"] == "SPOTIFY_NOT_CONFIGURED"
    assert "token" not in start.text.lower()


def test_shutdown_api_requires_confirmation_and_rejects_replay(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))
    headers = {"X-API-Key": "test-key"}
    requested = client.post("/command", headers=headers, json={"text": "關機"}).json()
    assert requested["confirmation_required"] is True
    token = requested["confirmation_token"]
    confirmed = client.post("/action", headers=headers, json={"action": "confirm_shutdown", "confirmation_token": token}).json()
    assert confirmed["success"] is True
    assert system.shutdown_calls == 1
    replay = client.post("/action", headers=headers, json={"action": "confirm_shutdown", "confirmation_token": token}).json()
    assert replay["success"] is False
    assert replay["error_code"] == "SHUTDOWN_TOKEN_REUSED"


def test_command_clarification_token_routes_only_to_server_owned_spotify_context(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    calls = []

    class FakeClarificationSpotify:
        def execute_clarification(self, text, clarification_token):
            calls.append((text, clarification_token))
            return OperationResult(True, "已播放 Stay。", data={"track_name": "Stay"})

    runtime.command_service.spotify = FakeClarificationSpotify()
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post(
        "/command",
        headers={"X-API-Key": "test-key"},
        json={"text": "第二首", "clarification_token": "opaque-server-token"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["action"] == "spotify_play_track"
    assert calls == [("第二首", "opaque-server-token")]


def test_command_clarification_request_rejects_client_track_targets(fake_runtime):
    runtime, launcher, process, media, volume, system = fake_runtime
    client = TestClient(create_app(runtime, refresh_on_startup=False, test_mode=True))

    response = client.post(
        "/command",
        headers={"X-API-Key": "test-key"},
        json={
            "text": "第一首",
            "clarification_token": "opaque-server-token",
            "track_uri": "spotify:track:client-supplied",
        },
    )

    assert response.status_code == 422
