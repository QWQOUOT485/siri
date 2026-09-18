"""Small rule-based Traditional Chinese/English command parser."""

from __future__ import annotations

import re

from app.domain.actions import ActionName, ParsedCommand, SpotifyVersionHint, ValidatedAction
from app.domain.matching import normalize_name


class CommandParser:
    def __init__(self, website_aliases: tuple[str, ...] = ()) -> None:
        self.website_aliases = {normalize_name(value) for value in website_aliases}

    def parse(self, text: str) -> ParsedCommand:
        raw = (text or "").strip()
        if not raw or len(raw) > 300:
            return ParsedCommand(accepted=False, error_code="INVALID_COMMAND", message="請提供簡短的控制指令。")
        if any(ord(char) < 32 or ord(char) == 127 for char in raw):
            return ParsedCommand(accepted=False, error_code="INVALID_COMMAND", message="請不要在指令中加入控制字元。")
        normalized = normalize_name(raw.rstrip("。！？!?."))

        exact = {
            "關機": ActionName.REQUEST_SHUTDOWN,
            "關閉電腦": ActionName.REQUEST_SHUTDOWN,
            "shutdown": ActionName.REQUEST_SHUTDOWN,
            "shut down": ActionName.REQUEST_SHUTDOWN,
            "power off": ActionName.REQUEST_SHUTDOWN,
            "鎖定": ActionName.LOCK,
            "鎖定電腦": ActionName.LOCK,
            "鎖電腦": ActionName.LOCK,
            "lock": ActionName.LOCK,
            "lock pc": ActionName.LOCK,
            "lock computer": ActionName.LOCK,
            "重新掃描程式": ActionName.REFRESH_APPS,
            "更新程式清單": ActionName.REFRESH_APPS,
            "refresh apps": ActionName.REFRESH_APPS,
            "播放音樂": ActionName.SPOTIFY_RESUME,
            "繼續播放": ActionName.SPOTIFY_RESUME,
            "播放": ActionName.SPOTIFY_RESUME,
            "play": ActionName.SPOTIFY_RESUME,
            "resume": ActionName.SPOTIFY_RESUME,
            "spotify play": ActionName.SPOTIFY_RESUME,
            "spotify resume": ActionName.SPOTIFY_RESUME,
            "暫停": ActionName.SPOTIFY_PAUSE,
            "pause": ActionName.SPOTIFY_PAUSE,
            "spotify pause": ActionName.SPOTIFY_PAUSE,
            "下一首": ActionName.SPOTIFY_NEXT,
            "下一曲": ActionName.SPOTIFY_NEXT,
            "next track": ActionName.SPOTIFY_NEXT,
            "next": ActionName.SPOTIFY_NEXT,
            "spotify next": ActionName.SPOTIFY_NEXT,
            "上一首": ActionName.SPOTIFY_PREVIOUS,
            "上一曲": ActionName.SPOTIFY_PREVIOUS,
            "previous track": ActionName.SPOTIFY_PREVIOUS,
            "previous": ActionName.SPOTIFY_PREVIOUS,
            "spotify previous": ActionName.SPOTIFY_PREVIOUS,
            "靜音": ActionName.MUTE,
            "mute": ActionName.MUTE,
            "取消靜音": ActionName.UNMUTE,
            "解除靜音": ActionName.UNMUTE,
            "unmute": ActionName.UNMUTE,
            "切換靜音": ActionName.TOGGLE_MUTE,
            "toggle mute": ActionName.TOGGLE_MUTE,
        }
        if normalized in exact:
            return self._accepted(exact[normalized])

        if normalized in {"play pause", "play/pause"}:
            return ParsedCommand(accepted=False, error_code="UNSUPPORTED_COMMAND", message="V1 不提供通用系統媒體播放切換，請使用 Spotify 指令。")

        spotify_track = self._spotify_track(raw.rstrip("。！？!?"))
        if spotify_track is not None:
            track, artist, album, version_hint = spotify_track
            return self._accepted(
                ActionName.SPOTIFY_PLAY_TRACK,
                track=track,
                artist=artist,
                album=album,
                version_hint=version_hint,
            )

        if self._unsafe(raw, normalized):
            return ParsedCommand(accepted=False, error_code="UNSUPPORTED_COMMAND", message="這個指令包含不支援或不安全的操作。")

        if normalized in {"音量大一點", "音量增加", "聲音大一點", "調大音量", "volume up", "increase volume"}:
            return self._accepted(ActionName.VOLUME_UP)
        if normalized in {"音量小一點", "音量降低", "聲音小一點", "調小音量", "volume down", "decrease volume"}:
            return self._accepted(ActionName.VOLUME_DOWN)

        force = re.match(r"^(?:強制關閉|強制結束|強制退出|強制終止|直接砍掉)\s*(.+)$", raw)
        force = force or re.match(r"^force(?:fully)?\s+(?:close|quit|kill)\s+(.+)$", raw, flags=re.IGNORECASE)
        if force:
            target = force.group(1).strip()
            if self._unsafe_target(target):
                return ParsedCommand(accepted=False, error_code="UNSUPPORTED_COMMAND", message="不接受路徑或命令列作為程式目標。")
            return self._accepted(ActionName.FORCE_CLOSE_APP, app_query=target)

        open_match = re.match(r"^(?:開啟|打開|啟動|開)\s*(.+)$", raw)
        open_match = open_match or re.match(r"^(?:open|launch|start)\s+(.+)$", raw, flags=re.IGNORECASE)
        if open_match:
            target = open_match.group(1).strip()
            if self._unsafe_target(target):
                return ParsedCommand(accepted=False, error_code="UNSUPPORTED_COMMAND", message="不接受路徑、網址或命令列作為目標。")
            target_normalized = normalize_name(target)
            if target_normalized in self.website_aliases:
                return self._accepted(ActionName.OPEN_WEBSITE, website_query=target)
            return self._accepted(ActionName.OPEN_APP, app_query=target)

        close_match = re.match(r"^(?:關閉|關掉|退出|關)\s*(.+)$", raw)
        close_match = close_match or re.match(r"^(?:close|quit|exit)\s+(.+)$", raw, flags=re.IGNORECASE)
        if close_match:
            target = close_match.group(1).strip()
            if self._unsafe_target(target):
                return ParsedCommand(accepted=False, error_code="UNSUPPORTED_COMMAND", message="不接受路徑或命令列作為程式目標。")
            return self._accepted(ActionName.CLOSE_APP, app_query=target)

        return ParsedCommand(accepted=False, error_code="INVALID_COMMAND", message="聽不懂這個安全指令，請改說開啟、關閉、播放、音量、鎖定或關機。")

    @staticmethod
    def _accepted(action: ActionName, **kwargs) -> ParsedCommand:
        return ParsedCommand(accepted=True, action=ValidatedAction(action=action, **kwargs), message="已解析指令。")

    @staticmethod
    def _spotify_track(raw: str) -> tuple[str, str | None, str | None, SpotifyVersionHint | None] | None:
        raw, version_hint = CommandParser._split_version_hint(raw)
        raw, album = CommandParser._split_album_hint(raw)
        raw, natural_album = CommandParser._split_natural_album_hint(raw)
        album = album or natural_album
        chinese = re.match(r"^(?:spotify\s*)?播放\s*(?P<artist>.+?)的(?P<track>.+)$", raw, flags=re.IGNORECASE)
        if chinese:
            artist = chinese.group("artist").strip()
            track = chinese.group("track").strip()
            return (track, artist, album, version_hint) if track and artist else None

        english = re.match(r"^(?:spotify\s+)?play\s+(?P<track>.+?)\s+by\s+(?P<artist>.+)$", raw, flags=re.IGNORECASE)
        if english:
            track = english.group("track").strip()
            artist = english.group("artist").strip()
            return (track, artist, album, version_hint) if track and artist else None

        chinese_track = re.match(r"^(?:spotify\s*)?播放\s*(?P<track>.+)$", raw, flags=re.IGNORECASE)
        if chinese_track:
            track = chinese_track.group("track").strip()
            return (track, None, album, version_hint) if track else None

        english_track = re.match(r"^(?:spotify\s+)?play\s+(?P<track>.+)$", raw, flags=re.IGNORECASE)
        if english_track:
            track = english_track.group("track").strip()
            return (track, None, album, version_hint) if track else None
        return None

    @staticmethod
    def _split_album_hint(raw: str) -> tuple[str, str | None]:
        """Treat one trailing parenthesized value as Spotify search metadata."""

        match = re.search(r"\s*[（(]\s*(?P<album>[^()（）]+?)\s*[）)]\s*$", raw)
        if not match:
            return raw, None
        album = match.group("album").strip()
        base = raw[: match.start()].rstrip()
        return (base, album) if base and album else (raw, None)

    @staticmethod
    def _split_natural_album_hint(raw: str) -> tuple[str, str | None]:
        """Extract album wording that Siri can naturally dictate."""

        leading = re.match(
            r"^(?P<prefix>(?:spotify\s*)?播放\s*)(?P<album>.+?)(?:專輯|专辑)\s*的\s*(?P<track>.+)$",
            raw,
            flags=re.IGNORECASE,
        )
        if leading:
            album = leading.group("album").strip()
            base = f"{leading.group('prefix')}{leading.group('track').strip()}"
            return (base, album) if base and album else (raw, None)

        english = re.search(r"\s+from\s+(?:the\s+)?album\s+(?P<album>.+?)\s*$", raw, flags=re.IGNORECASE)
        if english:
            album = english.group("album").strip()
            base = raw[: english.start()].rstrip()
            return (base, album) if base and album else (raw, None)

        trailing = re.search(
            r"(?:[，,、]\s*|\s+)(?:專輯|专辑|album)\s*(?:是|為|为|[:：])?\s*(?P<album>.+?)\s*$",
            raw,
            flags=re.IGNORECASE,
        )
        if not trailing:
            return raw, None
        album = trailing.group("album").strip()
        base = raw[: trailing.start()].rstrip(" ，,、")
        return (base, album) if base and album else (raw, None)

    @staticmethod
    def _split_version_hint(raw: str) -> tuple[str, SpotifyVersionHint | None]:
        """Extract only closed, safe version words from the end of a track phrase."""

        patterns = (
            (
                r"(?:現場版|现场版|演唱會版|演唱会版|演唱會|演唱会|live(?:\s+version)?|concert(?:\s+version)?)",
                SpotifyVersionHint.LIVE,
            ),
            (
                r"(?:錄音室版|录音室版|錄音室|录音室|studio(?:\s+version)?)",
                SpotifyVersionHint.STUDIO,
            ),
            (
                r"(?:原版|原始版|正式版|original(?:\s+version)?)",
                SpotifyVersionHint.ORIGINAL,
            ),
        )
        for suffix, hint in patterns:
            match = re.search(rf"\s*{suffix}\s*$", raw, flags=re.IGNORECASE)
            if not match:
                continue
            base = raw[: match.start()].rstrip(" ，,、")
            return (base, hint) if base else (raw, None)
        return raw, None

    @staticmethod
    def _unsafe_target(target: str) -> bool:
        return bool(re.search(r"(?:[A-Za-z]:[\\/]|\\\\|/|\.exe\b|\.bat\b|\.cmd\b|https?://|[;&|`$<>]|\x00)", target, flags=re.IGNORECASE))

    @classmethod
    def _unsafe(cls, raw: str, normalized: str) -> bool:
        if re.search(r"[;&|`$<>]", raw) or "\x00" in raw:
            return True
        if re.search(r"(?:cmd\s*/c|powershell(?:\.exe)?\s+-(?:command|enc)|pwsh\s+-|python\s+-c)", raw, flags=re.IGNORECASE):
            return True
        destructive = re.search(r"(?:刪除|删除|格式化|清空|rm\b|del\b|format\b|remove-item|shutdown\s+/)", raw, flags=re.IGNORECASE)
        conjunction = re.search(r"(?:然後|然后|and then|\bthen\b|之後|之后)", raw, flags=re.IGNORECASE)
        return bool(destructive and conjunction)
