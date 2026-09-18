from app.domain.actions import ActionName
from app.services.command_parser import CommandParser


def parser():
    return CommandParser(("YouTube Music", "youtube music"))


def test_chinese_and_english_commands():
    assert parser().parse("開啟 Discord").action.action is ActionName.OPEN_APP
    assert parser().parse("close Discord").action.action is ActionName.CLOSE_APP
    assert parser().parse("播放音樂").action.action is ActionName.SPOTIFY_RESUME
    assert parser().parse("暫停音樂").action.action is ActionName.SPOTIFY_PAUSE
    assert parser().parse("next track").action.action is ActionName.SPOTIFY_NEXT
    assert parser().parse("音量大一點").action.action is ActionName.VOLUME_UP
    assert parser().parse("鎖定電腦").action.action is ActionName.LOCK
    assert parser().parse("重新掃描程式").action.action is ActionName.REFRESH_APPS


def test_chinese_skip_commands_require_the_explicit_song_word():
    next_song = parser().parse("下一首歌")
    assert next_song.accepted is True
    assert next_song.action is not None
    assert next_song.action.action is ActionName.SPOTIFY_NEXT

    previous_song = parser().parse("上一首歌")
    assert previous_song.accepted is True
    assert previous_song.action is not None
    assert previous_song.action.action is ActionName.SPOTIFY_PREVIOUS

    for text in ("下一首", "下一曲", "上一首", "上一曲"):
        parsed = parser().parse(text)
        assert parsed.accepted is False, text


def test_website_and_force_close_are_explicit():
    assert parser().parse("打開 YouTube Music").action.action is ActionName.OPEN_WEBSITE
    force = parser().parse("強制關閉 Discord")
    assert force.action and force.action.action is ActionName.FORCE_CLOSE_APP
    normal = parser().parse("關閉 Discord")
    assert normal.action and normal.action.action is ActionName.CLOSE_APP


def test_shutdown_requires_a_second_stage_in_service():
    result = parser().parse("關機")
    assert result.action and result.action.action is ActionName.REQUEST_SHUTDOWN


def test_malicious_or_arbitrary_targets_are_rejected():
    for text in (
        r"open C:\Windows\System32\cmd.exe",
        "powershell -command Remove-Item C:\\",
        "cmd /c shutdown /s",
        "Discord && shutdown /s",
        "Discord; rm -rf /",
        "開 PowerShell 然後刪除 C 槽",
        "open https://evil.example/",
    ):
        parsed = parser().parse(text)
        assert parsed.accepted is False, text


def test_track_text_is_search_data_and_never_becomes_a_second_command():
    parsed = parser().parse("播放 A; rm -rf /")

    assert parsed.accepted is True
    assert parsed.action is not None
    assert parsed.action.action is ActionName.SPOTIFY_PLAY_TRACK
    assert parsed.action.track == "A; rm -rf /"


def test_generic_media_playback_is_not_a_remote_action_anymore():
    parsed = parser().parse("play pause")

    assert parsed.accepted is False
