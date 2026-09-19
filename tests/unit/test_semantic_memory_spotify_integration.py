import json
from pathlib import Path

import httpx

from app.adapters.spotify.catalog import SpotifyCatalog
from app.adapters.spotify.client import SpotifyApiClient
from app.adapters.spotify.player import SpotifyPlayer
from app.domain.actions import ActionName, ValidatedAction
from app.infrastructure.semantic_memory_db import SemanticMemoryDatabase
from app.infrastructure.spotify_auth import SpotifyAuthManager, SpotifyToken, SpotifyTokenStore
from app.services.alias_memory import AliasMemory
from app.services.entity_normalizer import EntityNormalizer
from app.services.entity_recovery import EntityRecoveryService
from app.services.memory_learner import MemoryLearner
from app.services.spotify_service import SpotifyService


def spotify_track(track_id: str, artist_id: str, artist_name: str = "SASIOVERLXRD") -> dict:
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": "Stay",
        "artists": [{"id": artist_id, "name": artist_name}],
        "album": {"name": "Album"},
    }


def build_service(tmp_path: Path, handler, *, playback_success: bool = True):
    client = SpotifyApiClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    store = SpotifyTokenStore(tmp_path / "spotify_token.json")
    store.save(
        SpotifyToken(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=10_000,
            scope="user-read-playback-state user-modify-playback-state",
        )
    )
    auth = SpotifyAuthManager(
        client_id="client-id",
        redirect_uri="http://127.0.0.1:8000/spotify/callback",
        token_store=store,
        client=client,
        clock=lambda: 1_000,
    )
    database = SemanticMemoryDatabase(tmp_path / "semantic.sqlite3")
    memory = AliasMemory(database)
    normalizer = EntityNormalizer()
    learner = MemoryLearner(database, memory, normalizer)
    recovery = EntityRecoveryService(memory, normalizer)
    catalog = SpotifyCatalog(client)
    player = SpotifyPlayer(client, device_name="Windows Spotify", sleep=lambda _seconds: None, device_retries=0)
    service = SpotifyService(
        auth,
        catalog,
        player,
        entity_recovery=recovery,
        memory_learner=learner,
    )
    return service, memory


def test_sad_overlxrd_first_clarification_then_exact_memory_hit(tmp_path: Path):
    search_queries: list[str] = []
    playback_calls = 0

    def handler(request: httpx.Request):
        nonlocal playback_calls
        if request.url.path == "/v1/search":
            query = request.url.params["q"]
            search_queries.append(query)
            if "artist:SASIOVERLXRD" in query:
                return httpx.Response(200, json={"tracks": {"items": [spotify_track("one", "artist123")]}})
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("one", "artist123"),
                            spotify_track("two", "artist123"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            playback_calls += 1
            assert json.loads(request.content) in ({"uris": ["spotify:track:one"]}, {"uris": ["spotify:track:two"]})
            return httpx.Response(204)
        raise AssertionError(request.url)

    service, memory = build_service(tmp_path, handler)
    command = ValidatedAction(
        action=ActionName.SPOTIFY_PLAY_TRACK,
        track="Stay",
        artist="Sad overlxrd",
    )

    first = service.execute(command)
    assert first.success is False
    assert first.error_code == "SPOTIFY_CLARIFICATION_REQUIRED"
    assert memory.lookup_exact("Sad overlxrd") is None

    selected = service.execute_clarification("第一首", first.data["clarification_token"])
    assert selected.success is True
    assert memory.lookup_exact("Sad overlxrd") is not None
    assert memory.lookup_exact("Sad overlxrd").entity.canonical_name == "SASIOVERLXRD"

    second = service.execute(command)
    assert second.success is True
    assert playback_calls == 2
    assert search_queries == [
        "track:Stay artist:Sad overlxrd",
        "track:Stay artist:SASIOVERLXRD",
    ]


def test_selected_candidate_with_failed_playback_does_not_confirm_alias(tmp_path: Path):
    def handler(request: httpx.Request):
        if request.url.path == "/v1/search":
            return httpx.Response(
                200,
                json={
                    "tracks": {
                        "items": [
                            spotify_track("one", "artist123"),
                            spotify_track("two", "artist123"),
                        ]
                    }
                },
            )
        if request.url.path == "/v1/me/library/contains":
            return httpx.Response(200, json=[False, False])
        if request.url.path in {"/v1/me/top/tracks", "/v1/me/top/artists"}:
            return httpx.Response(200, json={"items": []})
        if request.url.path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [{"id": "pc", "name": "Windows Spotify", "is_active": True}]})
        if request.url.path == "/v1/me/player/play":
            return httpx.Response(500, json={"error": {"status": 500, "message": "temporary"}})
        raise AssertionError(request.url)

    service, memory = build_service(tmp_path, handler)
    first = service.execute(
        ValidatedAction(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", artist="Sad overlxrd")
    )

    failed = service.execute_clarification("第一首", first.data["clarification_token"])

    assert failed.success is False
    assert memory.lookup_exact("Sad overlxrd") is None
