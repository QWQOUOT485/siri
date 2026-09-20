import pytest

from app.adapters.spotify.base import SpotifyDevice
from app.adapters.spotify.catalog import SpotifyTrackRef
from app.adapters.spotify.player import SpotifyPlayer
from app.adapters.windows.base import OperationResult


class FakeSpotifyPlayerClient:
    def __init__(self, devices, playback_states=None):
        self.devices = list(devices)
        self.playback_states = list(playback_states or [])
        self.calls = []

    def get_devices(self, access_token):
        self.calls.append(("devices", access_token))
        return self.devices

    def transfer_playback(self, access_token, device_id, *, play=False):
        self.calls.append(("transfer", access_token, device_id, play))

    def start_resume(self, access_token, *, device_id=None, track_uri=None):
        self.calls.append(("resume", access_token, device_id, track_uri))

    def pause(self, access_token, *, device_id=None):
        self.calls.append(("pause", access_token, device_id))

    def next(self, access_token, *, device_id=None):
        self.calls.append(("next", access_token, device_id))

    def previous(self, access_token, *, device_id=None):
        self.calls.append(("previous", access_token, device_id))

    def set_shuffle(self, access_token, enabled, *, device_id=None):
        self.calls.append(("shuffle", access_token, enabled, device_id))

    def set_repeat(self, access_token, mode, *, device_id=None):
        self.calls.append(("repeat", access_token, mode, device_id))

    def get_current_playback(self, access_token):
        self.calls.append(("playback", access_token))
        return self.playback_states.pop(0) if self.playback_states else {}


def test_player_selects_configured_device_transfers_it_then_plays_trusted_track():
    client = FakeSpotifyPlayerClient(
        [
            SpotifyDevice(device_id="phone", name="Phone", is_active=True),
            SpotifyDevice(device_id="pc", name="My Windows", is_active=False),
        ]
    )
    player = SpotifyPlayer(client, device_name="My Windows", sleep=lambda _seconds: None)
    ref = SpotifyTrackRef(
        track_id="track-1",
        track_uri="spotify:track:track1",
        track_name="Stay",
        artist_names=("The Kid LAROI",),
        album_name="Album",
    )

    result = player.resume("access-token", ref)

    assert result.success is True
    assert client.calls == [
        ("devices", "access-token"),
        ("transfer", "access-token", "pc", False),
        ("resume", "access-token", "pc", "spotify:track:track1"),
    ]


def test_player_opens_spotify_through_injected_trusted_callback_when_no_device_exists():
    client = FakeSpotifyPlayerClient([])
    opened = []

    def open_spotify():
        opened.append(True)
        client.devices.append(SpotifyDevice(device_id="pc", name="Spotify Desktop", is_active=True))
        return OperationResult(True, "opened")

    player = SpotifyPlayer(client, open_spotify=open_spotify, sleep=lambda _seconds: None, device_retries=1)

    result = player.pause("access-token")

    assert result.success is True
    assert opened == [True]
    assert client.calls[-1] == ("pause", "access-token", "pc")


def test_player_next_keeps_playback_running_when_configured_device_is_inactive():
    client = FakeSpotifyPlayerClient(
        [
            SpotifyDevice(device_id="phone", name="Phone", is_active=True),
            SpotifyDevice(device_id="pc", name="My Windows", is_active=False),
        ],
        playback_states=[
            {"item": {"id": "old-track"}, "is_playing": False, "context": {"uri": "spotify:playlist:playlist-1"}},
            {"item": {"id": "new-track"}, "is_playing": False, "context": {"uri": "spotify:playlist:playlist-1"}},
        ],
    )
    player = SpotifyPlayer(client, device_name="My Windows", sleep=lambda _seconds: None)

    result = player.next("access-token")

    assert result.success is True
    assert client.calls == [
        ("devices", "access-token"),
        ("playback", "access-token"),
        ("transfer", "access-token", "pc", True),
        ("next", "access-token", "pc"),
        ("playback", "access-token"),
        ("resume", "access-token", "pc", None),
    ]


def test_player_next_resumes_the_new_track_after_skipping():
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="My Windows", is_active=True)],
        playback_states=[
            {"item": {"id": "old-track"}, "is_playing": False, "context": {"uri": "spotify:playlist:playlist-1"}},
            {"item": {"id": "new-track"}, "is_playing": False, "context": {"uri": "spotify:playlist:playlist-1"}},
        ],
    )
    player = SpotifyPlayer(client, device_name="My Windows", sleep=lambda _seconds: None)

    result = player.next("access-token")

    assert result.success is True
    assert client.calls == [
        ("devices", "access-token"),
        ("playback", "access-token"),
        ("next", "access-token", "pc"),
        ("playback", "access-token"),
        ("resume", "access-token", "pc", None),
    ]


def test_player_next_does_not_resume_when_new_track_is_already_playing():
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="My Windows", is_active=True)],
        playback_states=[
            {"item": {"id": "old-track"}, "is_playing": True, "context": {"uri": "spotify:playlist:playlist-1"}},
            {"item": {"id": "new-track"}, "is_playing": True, "context": {"uri": "spotify:playlist:playlist-1"}},
        ],
    )
    player = SpotifyPlayer(client, device_name="My Windows", sleep=lambda _seconds: None)

    result = player.next("access-token")

    assert result.success is True
    assert ("resume", "access-token", "pc", None) not in client.calls


def test_player_next_does_not_restart_current_track_when_spotify_has_no_next_item():
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="My Windows", is_active=True)],
        playback_states=[
            {"item": {"id": "same-track"}, "is_playing": False, "context": {"uri": "spotify:album:album-1"}},
            {"item": {"id": "same-track"}, "is_playing": False, "context": {"uri": "spotify:album:album-1"}},
        ],
    )
    player = SpotifyPlayer(client, device_name="My Windows", sleep=lambda _seconds: None)

    result = player.next("access-token")

    assert result.success is False
    assert result.error_code == "SPOTIFY_NO_NEXT_TRACK"
    assert ("resume", "access-token", "pc", None) not in client.calls


def test_player_next_does_not_send_skip_for_a_standalone_track_without_context():
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="My Windows", is_active=True)],
        playback_states=[
            {"item": {"id": "same-track"}, "is_playing": True, "progress_ms": 1040, "context": None},
        ],
    )
    player = SpotifyPlayer(client, device_name="My Windows", sleep=lambda _seconds: None)

    result = player.next("access-token")

    assert result.success is False
    assert result.error_code == "SPOTIFY_NO_NEXT_TRACK"
    assert ("next", "access-token", "pc") not in client.calls
    assert ("resume", "access-token", "pc", None) not in client.calls


def test_player_reports_missing_device_without_shell_fallback():
    client = FakeSpotifyPlayerClient([])
    player = SpotifyPlayer(client, open_spotify=lambda: OperationResult(False, "not found", "UNKNOWN_APP"), sleep=lambda _seconds: None, device_retries=1)

    result = player.next("access-token")

    assert result.success is False
    assert result.error_code == "SPOTIFY_DEVICE_NOT_FOUND"
    assert "shell" not in result.message.lower()


def test_configured_device_name_does_not_fall_back_to_a_different_active_device():
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="phone", name="Phone", is_active=True)]
    )
    player = SpotifyPlayer(client, device_name="Windows Spotify", sleep=lambda _seconds: None, device_retries=0)

    result = player.pause("access-token")

    assert result.success is False
    assert result.error_code == "SPOTIFY_DEVICE_NOT_FOUND"
    assert client.calls == [("devices", "access-token")]


@pytest.mark.parametrize("enabled", [True, False])
def test_player_shuffle_routes_only_the_closed_boolean_state_to_the_selected_device(enabled):
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="Windows Spotify", is_active=True)]
    )
    player = SpotifyPlayer(client, device_name="Windows Spotify", sleep=lambda _seconds: None, device_retries=0)

    result = player.shuffle("access-token", enabled=enabled)

    assert result.success is True
    assert client.calls == [
        ("devices", "access-token"),
        ("shuffle", "access-token", enabled, "pc"),
    ]


@pytest.mark.parametrize("mode", ["off", "track", "context"])
def test_player_repeat_routes_only_closed_modes_to_the_selected_device(mode):
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="Windows Spotify", is_active=True)]
    )
    player = SpotifyPlayer(client, device_name="Windows Spotify", sleep=lambda _seconds: None, device_retries=0)

    result = player.repeat("access-token", mode)

    assert result.success is True
    assert client.calls == [
        ("devices", "access-token"),
        ("repeat", "access-token", mode, "pc"),
    ]


def test_player_rejects_free_form_repeat_mode_before_device_resolution():
    client = FakeSpotifyPlayerClient([])
    player = SpotifyPlayer(client, sleep=lambda _seconds: None, device_retries=0)

    result = player.repeat("access-token", "playlist")

    assert result.success is False
    assert result.error_code == "INVALID_SPOTIFY_REPEAT"
    assert client.calls == []


def test_player_continue_disables_repeat_then_resumes_without_reading_or_changing_shuffle():
    client = FakeSpotifyPlayerClient(
        [SpotifyDevice(device_id="pc", name="Windows Spotify", is_active=False)]
    )
    player = SpotifyPlayer(client, device_name="Windows Spotify", sleep=lambda _seconds: None, device_retries=0)

    result = player.continue_playback("access-token")

    assert result.success is True
    assert client.calls == [
        ("devices", "access-token"),
        ("transfer", "access-token", "pc", False),
        ("repeat", "access-token", "off", "pc"),
        ("resume", "access-token", "pc", None),
    ]
    assert not any(call[0] == "playback" for call in client.calls)
