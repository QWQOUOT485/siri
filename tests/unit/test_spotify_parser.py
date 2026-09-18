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


def test_spotify_prefix_is_still_a_closed_spotify_command():
    parsed = CommandParser().parse("Spotify 播放周杰倫的晴天")

    assert parsed.accepted is True
    assert parsed.action is not None
    assert parsed.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert parsed.action.track == "晴天"
    assert parsed.action.artist == "周杰倫"
