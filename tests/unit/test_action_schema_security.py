import pytest
from pydantic import ValidationError

from app.api.schemas import ActionRequest
from app.domain.actions import ActionName, ValidatedAction


def test_action_schema_has_no_shell_or_path_escape_hatches():
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.OPEN_APP, app_name=r"C:\Windows\System32\cmd.exe")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.OPEN_WEBSITE, website_name="https://evil.example")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.OPEN_APP, app_name="Discord", command="whoami")
    with pytest.raises(ValidationError):
        ValidatedAction(action=ActionName.OPEN_APP, app_query="Discord", executable_path="C:\\bad.exe")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.SPOTIFY_PLAY_TRACK, track="Stay", track_uri="spotify:track:client_supplied")
    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.SPOTIFY_PAUSE, album="Album must not be accepted here")
    with pytest.raises(ValidationError):
        ActionRequest(action="media_play", app_name="ignored")


def test_spotify_album_hint_stays_search_data():
    action = ActionRequest(
        action=ActionName.SPOTIFY_PLAY_TRACK,
        track="晴天",
        artist="周杰倫",
        album="葉惠美",
    ).to_validated()

    assert action.album == "葉惠美"


def test_spotify_version_hint_is_closed_search_data_only():
    action = ActionRequest(
        action=ActionName.SPOTIFY_PLAY_TRACK,
        track="晴天",
        artist="周杰倫",
        version_hint="live",
    ).to_validated()

    assert action.version_hint.value == "live"

    with pytest.raises(ValidationError):
        ActionRequest(
            action=ActionName.SPOTIFY_PLAY_TRACK,
            track="晴天",
            version_hint="live; shutdown /s",
        )

    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.SPOTIFY_PAUSE, version_hint="live")


def test_spotify_metadata_accepts_long_but_bounded_values():
    value = "長" * 250
    action = ActionRequest(
        action=ActionName.SPOTIFY_PLAY_TRACK,
        track=value,
        artist=value,
        album=value,
    ).to_validated()

    assert action.track == value
    assert action.artist == value
    assert action.album == value

    with pytest.raises(ValidationError):
        ActionRequest(
            action=ActionName.SPOTIFY_PLAY_TRACK,
            track="長" * 301,
        )


def test_exact_volume_schema_accepts_only_bounded_values_and_its_own_field():
    assert ActionRequest(action="set_volume", volume_percent=0).to_validated().volume_percent == 0
    assert ActionRequest(action="set_volume", volume_percent=100).to_validated().volume_percent == 100

    for value in (-1, 101):
        with pytest.raises(ValidationError):
            ActionRequest(action="set_volume", volume_percent=value)

    for value in (37.5, "37", True):
        with pytest.raises(ValidationError):
            ActionRequest(action="set_volume", volume_percent=value)

    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.VOLUME_UP, volume_percent=37)


def test_extended_spotify_controls_are_closed_actions_without_client_state_fields():
    for action in (
        ActionName.SPOTIFY_SHUFFLE_ON,
        ActionName.SPOTIFY_SHUFFLE_OFF,
        ActionName.SPOTIFY_REPEAT_OFF,
        ActionName.SPOTIFY_REPEAT_TRACK,
        ActionName.SPOTIFY_REPEAT_CONTEXT,
        ActionName.SPOTIFY_CONTINUE,
    ):
        assert ActionRequest(action=action).to_validated().action is action

    with pytest.raises(ValidationError):
        ActionRequest(action=ActionName.SPOTIFY_REPEAT_TRACK, repeat_mode="playlist")

    with pytest.raises(ValidationError):
        ValidatedAction(action=ActionName.SPOTIFY_REPEAT_TRACK, steps=2)
