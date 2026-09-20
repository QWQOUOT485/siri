import pytest

from app.domain.actions import ActionName
from app.services.command_parser import CommandParser


def test_bare_play_commands_target_spotify_resume():
    parser = CommandParser()

    for text in ("播放", "播放音樂", "繼續播放", "play", "resume"):
        parsed = parser.parse(text)
        assert parsed.accepted is True
        assert parsed.action is not None
        assert parsed.action.action is ActionName.SPOTIFY_RESUME


def test_named_track_commands_capture_track_and_optional_artist():
    parser = CommandParser()

    track_only = parser.parse("播放晴天")
    assert track_only.action is not None
    assert track_only.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert track_only.action.track == "晴天"
    assert track_only.action.artist is None

    with_artist = parser.parse("播放周杰倫的晴天")
    assert with_artist.action is not None
    assert with_artist.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert with_artist.action.track == "晴天"
    assert with_artist.action.artist == "周杰倫"


def test_english_named_track_command_uses_spotify_action():
    parsed = CommandParser().parse("Play Blinding Lights by The Weeknd")

    assert parsed.accepted is True
    assert parsed.action is not None
    assert parsed.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert parsed.action.track == "Blinding Lights"
    assert parsed.action.artist == "The Weeknd"


def test_named_track_command_captures_a_parenthesized_album_hint():
    parsed = CommandParser().parse("播放周杰倫的晴天 (葉惠美)")

    assert parsed.accepted is True
    assert parsed.action is not None
    assert parsed.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert parsed.action.track == "晴天"
    assert parsed.action.artist == "周杰倫"
    assert parsed.action.album == "葉惠美"


def test_natural_chinese_album_phrases_are_search_hints_not_track_text():
    trailing_album = CommandParser().parse("播放周杰倫的晴天，專輯葉惠美")
    assert trailing_album.accepted is True
    assert trailing_album.action is not None
    assert trailing_album.action.track == "晴天"
    assert trailing_album.action.artist == "周杰倫"
    assert trailing_album.action.album == "葉惠美"

    leading_album = CommandParser().parse("播放葉惠美專輯的晴天")
    assert leading_album.accepted is True
    assert leading_album.action is not None
    assert leading_album.action.track == "晴天"
    assert leading_album.action.artist is None
    assert leading_album.action.album == "葉惠美"


def test_natural_version_phrases_capture_closed_version_intent():
    live = CommandParser().parse("播放周杰倫的晴天現場版")
    assert live.accepted is True
    assert live.action is not None
    assert live.action.track == "晴天"
    assert live.action.artist == "周杰倫"
    assert live.action.version_hint == "live"

    original = CommandParser().parse("播放晴天原版")
    assert original.accepted is True
    assert original.action is not None
    assert original.action.track == "晴天"
    assert original.action.version_hint == "original"

    english_live = CommandParser().parse("Play Blinding Lights live")
    assert english_live.accepted is True
    assert english_live.action is not None
    assert english_live.action.track == "Blinding Lights"
    assert english_live.action.version_hint == "live"


def test_spotify_prefix_is_still_a_closed_spotify_command():
    parsed = CommandParser().parse("Spotify 播放周杰倫的晴天")

    assert parsed.accepted is True
    assert parsed.action is not None
    assert parsed.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert parsed.action.track == "晴天"
    assert parsed.action.artist == "周杰倫"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("隨機播放", ActionName.SPOTIFY_SHUFFLE_ON),
        ("開啟隨機播放", ActionName.SPOTIFY_SHUFFLE_ON),
        ("shuffle on", ActionName.SPOTIFY_SHUFFLE_ON),
        ("不要隨機", ActionName.SPOTIFY_SHUFFLE_OFF),
        ("關閉隨機播放", ActionName.SPOTIFY_SHUFFLE_OFF),
        ("shuffle off", ActionName.SPOTIFY_SHUFFLE_OFF),
        ("單曲循環", ActionName.SPOTIFY_REPEAT_TRACK),
        ("repeat this track", ActionName.SPOTIFY_REPEAT_TRACK),
        ("循環播放清單", ActionName.SPOTIFY_REPEAT_CONTEXT),
        ("repeat context", ActionName.SPOTIFY_REPEAT_CONTEXT),
        ("不要循環", ActionName.SPOTIFY_REPEAT_OFF),
        ("關閉循環", ActionName.SPOTIFY_REPEAT_OFF),
        ("repeat off", ActionName.SPOTIFY_REPEAT_OFF),
        ("正常播就好", ActionName.SPOTIFY_CONTINUE),
        ("continue normally", ActionName.SPOTIFY_CONTINUE),
    ],
)
def test_extended_spotify_controls_are_closed_parser_actions(text, expected):
    parsed = CommandParser().parse(text)

    assert parsed.accepted is True
    assert parsed.action is not None
    assert parsed.action.action is expected


def test_repeat_and_shuffle_phrases_do_not_cross_domains():
    parser = CommandParser()

    assert parser.parse("關閉隨機播放").action.action is ActionName.SPOTIFY_SHUFFLE_OFF
    assert parser.parse("關閉循環").action.action is ActionName.SPOTIFY_REPEAT_OFF
