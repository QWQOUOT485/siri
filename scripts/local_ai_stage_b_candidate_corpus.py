"""Build an offline, unsplit Stage B candidate corpus.

This module is deliberately separate from the reviewed final ``StageBRecord``
schema.  It generates provisional rows from a deterministic local synthetic
entity catalog, then projects them into ``StageBRecord`` only for validation.
The generator never reads Stage A while producing rows; the frozen Stage A
fixture is consulted only by the post-generation leakage check.

No network, subprocess, model, Spotify, LM Studio, Windows, or production
authority path is available from this module.  The generated rows are
candidate data and every row remains pending independent review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import local_ai_stage_b_corpus as protocol


CANDIDATE_SCHEMA_VERSION = 1
CANDIDATE_CORPUS_VERSION = "stage-b-candidate-corpus-v1"
GENERATOR_VERSION = "stage-b-candidate-generator-v2"
GENERATION_SOURCE = "synthetic_local_entity_catalog_v1"
REVIEW_STATUS = "pending_independent_review"
VARIANTS_PER_SOURCE_GROUP = 6
TARGET_CANDIDATE_ROWS = 3600
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024

SCOPE_ORDER = (
    "supported_play",
    "supported_unknown",
    "deterministic_only",
    "safety_only",
)
LANGUAGE_ORDER = ("zh-Hant", "zh-Hans", "mixed", "en")
SCOPE_TO_AI_SCOPE = {
    "supported_play": "supported",
    "supported_unknown": "supported",
    "deterministic_only": "deterministic_only",
    "safety_only": "safety_only",
}

GROUP_COUNTS = {
    "supported_play": 300,
    "supported_unknown": 210,
    "deterministic_only": 50,
    "safety_only": 40,
}

LANGUAGE_GROUP_COUNTS = {
    "supported_play": {"zh-Hant": 120, "zh-Hans": 24, "mixed": 90, "en": 66},
    "supported_unknown": {"zh-Hant": 80, "zh-Hans": 16, "mixed": 70, "en": 44},
    "deterministic_only": {"zh-Hant": 18, "zh-Hans": 4, "mixed": 18, "en": 10},
    "safety_only": {"zh-Hant": 12, "zh-Hans": 4, "mixed": 12, "en": 12},
}

PLAY_SLOT_MODES = (
    ("both", 120),
    ("artist_only", 60),
    ("album_only", 60),
    ("neither", 60),
)

UNKNOWN_REASONS = (
    "artist_only",
    "missing_track",
    "unresolved_reference",
    "ambiguous_version",
    "unsupported_domain",
)

DETERMINISTIC_REASONS = (
    "playback_control",
    "playback_control",
    "playback_control",
    "playback_control",
    "playback_control",
    "unsupported_domain",
)

SAFETY_REASONS = (
    "hostile_system",
    "path_or_url",
    "path_or_url",
    "hostile_system",
    "hostile_system",
    "hostile_system",
)

DETERMINISTIC_REASON_BY_VARIANT = {
    0: "playback_control",
    1: "playback_control",
    2: "playback_control",
    3: "playback_control",
    4: "playback_control",
    5: "unsupported_domain",
}
SAFETY_REASON_BY_VARIANT = {
    0: "hostile_system",
    1: "path_or_url",
    2: "path_or_url",
    3: "hostile_system",
    4: "hostile_system",
    5: "hostile_system",
}

ZH_HANT_HOMOPHONE_SURFACE = {
    "林": "淋",
    "周": "舟",
    "陳": "晨",
    "黃": "皇",
    "許": "許",
    "葉": "夜",
    "鄭": "正",
    "吳": "無",
    "蔡": "采",
    "雨": "語",
    "紙": "只",
    "霧": "務",
    "藍": "蘭",
    "遠": "元",
    "月": "越",
    "星": "心",
    "春": "純",
    "光": "廣",
    "安": "岸",
    "時": "詩",
}
ZH_HANS_HOMOPHONE_SURFACE = {
    "林": "淋",
    "周": "舟",
    "陈": "晨",
    "黄": "皇",
    "许": "许",
    "叶": "夜",
    "郑": "正",
    "吴": "无",
    "蔡": "采",
    "雨": "语",
    "纸": "只",
    "雾": "务",
    "蓝": "兰",
    "远": "元",
    "月": "越",
    "星": "心",
    "春": "纯",
    "光": "广",
    "安": "岸",
    "时": "诗",
}

CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")

CANDIDATE_FIELDS = frozenset(
    {
        "candidate_id",
        "source_group_id",
        "utterance",
        "language_tag",
        "language_slice",
        "provisional_ai_scope",
        "provisional_expected",
        "provisional_optional_slot_status",
        "provisional_negative_reason",
        "template_family",
        "generation_source",
        "generator_version",
        "review_status",
    }
)

EXPECTED_FIELDS = frozenset({"intent", "track", "artist", "album"})


class CandidateCorpusError(ValueError):
    """A candidate build failed a deterministic safety or integrity check."""


@dataclass(frozen=True, slots=True)
class SyntheticEntity:
    """A local synthetic entity; it intentionally has no provider identity."""

    entity_key: str
    language_tag: str
    artist: str
    track: str
    album: str

    def to_dict(self) -> dict[str, str]:
        return {
            "entity_key": self.entity_key,
            "language_tag": self.language_tag,
            "artist": self.artist,
            "track": self.track,
            "album": self.album,
        }


@dataclass(frozen=True, slots=True)
class GroupPlan:
    source_group_id: str
    scope: str
    language_tag: str
    entity: SyntheticEntity
    slot_mode: str | None
    negative_reason: str | None


@dataclass(frozen=True, slots=True)
class StageBCandidateRecord:
    """Separate provisional candidate schema, not final Stage B authority."""

    candidate_id: str
    source_group_id: str
    utterance: str
    language_tag: str
    language_slice: str
    provisional_ai_scope: str
    provisional_expected: protocol.StageBExpected
    provisional_optional_slot_status: Mapping[str, str] | None
    provisional_negative_reason: str | None
    template_family: str
    generation_source: str
    generator_version: str
    review_status: str

    def __post_init__(self) -> None:
        _require_text("candidate_id", self.candidate_id, 200)
        _require_text("source_group_id", self.source_group_id, 200)
        _require_text("utterance", self.utterance, 4000)
        _require_text("template_family", self.template_family, 200)
        _require_text("generation_source", self.generation_source, 200)
        _require_text("generator_version", self.generator_version, 200)
        if self.review_status != REVIEW_STATUS:
            raise CandidateCorpusError("every candidate review_status must remain pending")
        if self.language_tag not in protocol.ALLOWED_LANGUAGE_SLICE_BY_TAG:
            raise CandidateCorpusError("candidate language_tag is outside the closed enum")
        if self.language_slice != protocol.ALLOWED_LANGUAGE_SLICE_BY_TAG[self.language_tag]:
            raise CandidateCorpusError("candidate language mapping is inconsistent")
        if self.provisional_ai_scope not in {
            member.value for member in protocol.StageBAIScope
        }:
            raise CandidateCorpusError("candidate ai scope is outside the closed enum")
        if self.provisional_negative_reason is not None and self.provisional_negative_reason not in {
            member.value for member in protocol.NegativeReason
        }:
            raise CandidateCorpusError("candidate negative reason is outside the closed enum")
        if self.provisional_optional_slot_status is not None:
            object.__setattr__(
                self,
                "provisional_optional_slot_status",
                MappingProxyType(dict(self.provisional_optional_slot_status)),
            )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "StageBCandidateRecord":
        if not isinstance(payload, Mapping):
            raise CandidateCorpusError("candidate must be an object")
        protocol._scan_forbidden_fields(payload)
        protocol._scan_sensitive_values(payload)
        if set(payload) != CANDIDATE_FIELDS:
            raise CandidateCorpusError("candidate fields do not match the closed schema")
        provisional_expected = payload["provisional_expected"]
        if not isinstance(provisional_expected, Mapping):
            raise CandidateCorpusError("provisional_expected must be an object")
        if set(provisional_expected) != EXPECTED_FIELDS:
            raise CandidateCorpusError("provisional_expected fields are not closed")
        stage_payload = {
            "case_id": payload["candidate_id"],
            "source_group_id": payload["source_group_id"],
            "utterance": payload["utterance"],
            "language_tag": payload["language_tag"],
            "language_slice": payload["language_slice"],
            "ai_scope": payload["provisional_ai_scope"],
            "expected": provisional_expected,
            "optional_slot_status": payload["provisional_optional_slot_status"],
            "negative_reason": payload["provisional_negative_reason"],
            "template_family": payload["template_family"],
            "generator_version": payload["generator_version"],
        }
        record = protocol.StageBRecord.from_mapping(stage_payload)
        generation_source = _require_text(
            "generation_source", payload["generation_source"], 200
        )
        review_status = _require_text("review_status", payload["review_status"], 80)
        if review_status != REVIEW_STATUS:
            raise CandidateCorpusError("candidate review_status must be pending")
        return cls(
            candidate_id=record.case_id,
            source_group_id=record.source_group_id,
            utterance=record.utterance,
            language_tag=record.language_tag,
            language_slice=record.language_slice,
            provisional_ai_scope=record.ai_scope,
            provisional_expected=record.expected,
            provisional_optional_slot_status=record.optional_slot_status,
            provisional_negative_reason=record.negative_reason,
            template_family=record.template_family,
            generation_source=generation_source,
            generator_version=record.generator_version,
            review_status=review_status,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_group_id": self.source_group_id,
            "utterance": self.utterance,
            "language_tag": self.language_tag,
            "language_slice": self.language_slice,
            "provisional_ai_scope": self.provisional_ai_scope,
            "provisional_expected": self.provisional_expected.to_dict(),
            "provisional_optional_slot_status": (
                dict(self.provisional_optional_slot_status)
                if self.provisional_optional_slot_status is not None
                else None
            ),
            "provisional_negative_reason": self.provisional_negative_reason,
            "template_family": self.template_family,
            "generation_source": self.generation_source,
            "generator_version": self.generator_version,
            "review_status": self.review_status,
        }

    def to_stage_b_record(self) -> protocol.StageBRecord:
        return protocol.StageBRecord.from_mapping(
            {
                "case_id": self.candidate_id,
                "source_group_id": self.source_group_id,
                "utterance": self.utterance,
                "language_tag": self.language_tag,
                "language_slice": self.language_slice,
                "ai_scope": self.provisional_ai_scope,
                "expected": self.provisional_expected.to_dict(),
                "optional_slot_status": (
                    dict(self.provisional_optional_slot_status)
                    if self.provisional_optional_slot_status is not None
                    else None
                ),
                "negative_reason": self.provisional_negative_reason,
                "template_family": self.template_family,
                "generator_version": self.generator_version,
            }
        )


def _require_text(name: str, value: Any, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CandidateCorpusError(f"{name} must be non-empty text")
    if len(value) > max_length:
        raise CandidateCorpusError(f"{name} exceeds its bound")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CandidateCorpusError(f"{name} contains a control character")
    return value


def _canonical_json(value: Any) -> str:
    return protocol.canonical_json(value)


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        + b"\n"
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value))


def _language_slice(language_tag: str) -> str:
    return protocol.ALLOWED_LANGUAGE_SLICE_BY_TAG[language_tag]


def _contains_cjk(value: str) -> bool:
    return CJK_RE.search(value) is not None


def _contains_ascii_letter(value: str) -> bool:
    return ASCII_LETTER_RE.search(value) is not None


def _validate_language_surface(language_tag: str, utterance: str) -> None:
    if language_tag == "mixed":
        if not _contains_cjk(utterance):
            raise CandidateCorpusError("mixed candidate must contain CJK text")
        if not _contains_ascii_letter(utterance):
            raise CandidateCorpusError(
                "mixed candidate must contain an ASCII English letter"
            )
    elif language_tag == "en" and _contains_cjk(utterance):
        raise CandidateCorpusError("English candidate must not contain CJK text")


def _render(segments: Sequence[tuple[str, str | None]]) -> tuple[str, dict[str, dict[str, Any]]]:
    pieces: list[str] = []
    spans: dict[str, dict[str, Any]] = {}
    offset = 0
    for text, role in segments:
        if not isinstance(text, str):
            raise CandidateCorpusError("template segment must be text")
        pieces.append(text)
        end = offset + len(text)
        if role is not None:
            if role in spans:
                raise CandidateCorpusError("a template may contain each slot only once")
            spans[role] = {"text": text, "start": offset, "end": end}
        offset = end
    return "".join(pieces), spans


def _display(
    value: str,
    language_tag: str,
    variant: int,
    *,
    corrupt: bool = False,
) -> str:
    """Apply one bounded entity-surface variation when this field is selected.

    ``corrupt`` is deliberately explicit so a row can never change every
    present entity merely because it uses an ASR-noise template.  Chinese
    variant 5 is represented by its carrier/template wording instead of a
    partial first-character Pinyin substitution.
    """

    if not corrupt:
        return value
    if language_tag in {"en", "mixed"}:
        if variant == 4:
            return value.lower()
        if variant == 5:
            return value.replace(" ", "")
    if language_tag == "zh-Hant" and variant == 4:
        for source, surface in ZH_HANT_HOMOPHONE_SURFACE.items():
            if value.startswith(source):
                return surface + value[len(source) :]
    if language_tag == "zh-Hans" and variant == 4:
        for source, surface in ZH_HANS_HOMOPHONE_SURFACE.items():
            if value.startswith(source):
                return surface + value[len(source) :]
    return value


def _play_segments(
    entity: SyntheticEntity,
    *,
    slot_mode: str,
    language_tag: str,
    variant: int,
) -> tuple[str, dict[str, dict[str, Any]], str]:
    # Keep entity noise bounded to the track surface.  The row may contain
    # artist and album too, but an ASR-noise row must not corrupt all slots by
    # construction.
    artist = _display(entity.artist, language_tag, variant)
    track = _display(
        entity.track,
        language_tag,
        variant,
        corrupt=variant in {4, 5},
    )
    album = _display(entity.album, language_tag, variant)
    has_artist = slot_mode in {"both", "artist_only"}
    has_album = slot_mode in {"both", "album_only"}

    if language_tag == "en":
        if variant == 0:
            segments = [("Play ", None), (track, "track")]
            if has_artist:
                segments += [(" by ", None), (artist, "artist")]
            if has_album:
                segments += [(" from ", None), (album, "album")]
            family = "play_en_direct"
        elif variant == 1:
            segments = [("I want to hear ", None), (track, "track")]
            if has_artist:
                segments += [(" by ", None), (artist, "artist")]
            if has_album:
                segments += [(" on the album ", None), (album, "album")]
            family = "play_en_conversational"
        elif variant == 2:
            segments = [("Put on ", None)]
            if has_album:
                segments += [(album, "album"), (" — ", None)]
            segments += [(track, "track")]
            if has_artist:
                segments += [(" by ", None), (artist, "artist")]
            family = "play_en_word_order"
        elif variant == 3:
            segments = [("Could you play ", None), (track, "track")]
            if has_album:
                segments += [(" from ", None), (album, "album")]
            if has_artist:
                segments += [(" by ", None), (artist, "artist")]
            segments += [(" for me?", None)]
            family = "play_en_polite"
        elif variant == 4:
            segments = [("Please queue ", None), (track, "track")]
            if has_artist:
                segments += [(" / ", None), (artist, "artist")]
            if has_album:
                segments += [(" / ", None), (album, "album")]
            family = "play_en_punctuation_loss"
        else:
            segments = [("Play ", None), (track, "track")]
            if has_artist:
                segments += [(" artist ", None), (artist, "artist")]
            if has_album:
                segments += [(" album ", None), (album, "album")]
            segments += [(" please", None)]
            family = "play_en_asr_spacing"
    elif language_tag == "zh-Hant":
        if variant == 0:
            segments = [("幫我播", None)]
            if has_artist:
                segments += [(artist, "artist"), ("的", None)]
            segments += [(track, "track")]
            if has_album:
                segments += [("，專輯是", None), (album, "album")]
            family = "play_hant_direct"
        elif variant == 1:
            segments = [("播放一下", None), (track, "track")]
            if has_artist:
                segments += [("，歌手是", None), (artist, "artist")]
            if has_album:
                segments += [("，收錄在", None), (album, "album")]
            family = "play_hant_conversational"
        elif variant == 2:
            segments = [("我要聽", None)]
            if has_album:
                segments += [(album, "album"), ("裡的", None)]
            if has_artist:
                segments += [(artist, "artist"), ("那首", None)]
            segments += [(track, "track")]
            family = "play_hant_word_order"
        elif variant == 3:
            segments = [("先放", None), (track, "track")]
            if has_artist:
                segments += [("，是", None), (artist, "artist")]
            if has_album:
                segments += [("專輯", None), (album, "album")]
            family = "play_hant_particle"
        elif variant == 4:
            segments = [("麻煩播", None)]
            if has_artist:
                segments += [(artist, "artist"), ("那張", None)]
            if has_album:
                segments += [(album, "album"), ("裡的", None)]
            segments += [(track, "track"), ("，謝謝", None)]
            family = "play_hant_homophone"
        else:
            segments = [("播一下", None), (track, "track"), ("，請幫我放", None)]
            if has_artist:
                segments += [(artist, "artist")]
            if has_album:
                segments += [("，專輯", None), (album, "album")]
            family = "play_hant_spacing"
    elif language_tag == "zh-Hans":
        if variant == 0:
            segments = [("帮我播", None)]
            if has_artist:
                segments += [(artist, "artist"), ("的", None)]
            segments += [(track, "track")]
            if has_album:
                segments += [("，专辑是", None), (album, "album")]
            family = "play_hans_direct"
        elif variant == 1:
            segments = [("播放一下", None), (track, "track")]
            if has_artist:
                segments += [("，歌手是", None), (artist, "artist")]
            if has_album:
                segments += [("，收录在", None), (album, "album")]
            family = "play_hans_conversational"
        elif variant == 2:
            segments = [("我要听", None)]
            if has_album:
                segments += [(album, "album"), ("里的", None)]
            if has_artist:
                segments += [(artist, "artist"), ("那首", None)]
            segments += [(track, "track")]
            family = "play_hans_word_order"
        elif variant == 3:
            segments = [("先放", None), (track, "track")]
            if has_artist:
                segments += [("，是", None), (artist, "artist")]
            if has_album:
                segments += [("专辑", None), (album, "album")]
            family = "play_hans_particle"
        elif variant == 4:
            segments = [("麻烦播", None)]
            if has_artist:
                segments += [(artist, "artist"), ("那张", None)]
            if has_album:
                segments += [(album, "album"), ("里的", None)]
            segments += [(track, "track"), ("，谢谢", None)]
            family = "play_hans_homophone"
        else:
            segments = [("播一下", None), (track, "track"), ("，请帮我放", None)]
            if has_artist:
                segments += [(artist, "artist")]
            if has_album:
                segments += [("，专辑", None), (album, "album")]
            family = "play_hans_spacing"
    else:
        if variant == 0:
            segments = [("幫我 play ", None), (track, "track")]
            if has_artist:
                segments += [(" by ", None), (artist, "artist")]
            if has_album:
                segments += [(" from ", None), (album, "album")]
            family = "play_mixed_code_switch"
        elif variant == 1:
            segments = [("我要聽 ", None)]
            if has_artist:
                segments += [(artist, "artist"), (" 的 ", None)]
            segments += [(track, "track")]
            if has_album:
                segments += [("，album 是 ", None), (album, "album")]
            family = "play_mixed_conversational"
        elif variant == 2:
            segments = [("Play 一下 ", None)]
            if has_album:
                segments += [(album, "album"), (" 裡的 ", None)]
            segments += [(track, "track")]
            if has_artist:
                segments += [("，artist 是 ", None), (artist, "artist")]
            family = "play_mixed_word_order"
        elif variant == 3:
            segments = [("放 ", None), (track, "track")]
            if has_artist:
                segments += [("，by ", None), (artist, "artist")]
            if has_album:
                segments += [("，album ", None), (album, "album")]
            family = "play_mixed_particle"
        elif variant == 4:
            segments = [("幫我播 ", None)]
            if has_artist:
                segments += [(artist, "artist"), (" 的 ", None)]
            segments += [(track, "track")]
            if has_album:
                segments += [("，專輯 ", None), (album, "album")]
            family = "play_mixed_asr_case"
        else:
            segments = [("請 play ", None), (track, "track")]
            if has_artist:
                segments += [(" ", None), (artist, "artist")]
            if has_album:
                segments += [(" ", None), (album, "album")]
            family = "play_mixed_asr_spacing"

    utterance, spans = _render(segments)
    return utterance, spans, family


def _unknown_utterance(
    entity: SyntheticEntity,
    *,
    language_tag: str,
    variant: int,
    reason: str,
) -> tuple[str, str]:
    artist = _display(entity.artist, language_tag, variant)
    track = _display(
        entity.track,
        language_tag,
        variant,
        corrupt=variant in {4, 5},
    )
    album = _display(entity.album, language_tag, variant)
    if language_tag == "en":
        templates = {
            "artist_only": [
                f"Play something by {artist}",
                f"I want {artist}",
                f"Put on {artist}",
                f"Can you play {artist}",
                f"Start music from {artist}",
                f"Play the artist {artist}",
            ],
            "missing_track": [
                f"Play something from the album {album}",
                f"I want the {album} album",
                f"Put on {album} by {artist}",
                f"Can you open the album {album}",
                f"Start a song from {album}",
                f"Find the {album} release",
            ],
            "unresolved_reference": [
                f"Play that one by {artist}",
                f"Play the one we mentioned from {artist}",
                f"Put on the previous song by {artist}",
                f"Use that track from {artist}",
                f"Play the other one by {artist}",
                f"Start the song I mean from {artist}",
            ],
            "ambiguous_version": [
                f"Should I play {track} live or the original version",
                f"Play {track} but I am unsure about the live version",
                f"I mean {track}, maybe live, maybe studio",
                f"Find {track} in the right version",
                f"Use the original or live {track}",
                f"Play {track} with the version undecided",
            ],
            "unsupported_domain": [
                f"What time is {artist} performing near me",
                f"Find concert dates for {artist}",
                f"Show lyrics for {track}",
                f"Tell me the release story of {album}",
                f"Search reviews of {track}",
                f"Open a video about {artist}",
            ],
        }[reason]
    elif language_tag == "zh-Hans":
        templates = {
            "artist_only": [
                f"播放{artist}的歌",
                f"我想听{artist}",
                f"放一下{artist}",
                f"帮我播放{artist}",
                f"先找{artist}的音乐",
                f"播放歌手{artist}",
            ],
            "missing_track": [
                f"播放专辑{album}里的歌",
                f"我想听{album}这张专辑",
                f"放{artist}的{album}",
                f"帮我打开专辑{album}",
                f"找一首{album}里的歌",
                f"查一下{album}这个发行",
            ],
            "unresolved_reference": [
                f"播放刚才提到的{artist}那首",
                f"就放{artist}刚刚那首",
                f"播放之前说的{artist}",
                f"用一下{artist}的那首",
                f"换成{artist}的另一首",
                f"开始播放我说的{artist}歌曲",
            ],
            "ambiguous_version": [
                f"播放{track}的现场版还是原版",
                f"我想听{track}但版本不确定",
                f"{track}要现场还是录音室版",
                f"找一下正确版本的{track}",
                f"用{track}的原版或现场版",
                f"播放{track}，版本先不确定",
            ],
            "unsupported_domain": [
                f"查{artist}最近的演出时间",
                f"找{artist}的演唱会日期",
                f"显示{track}的歌词",
                f"告诉我{album}的发行故事",
                f"搜索{track}的评论",
                f"打开关于{artist}的视频",
            ],
        }[reason]
    elif language_tag == "zh-Hant":
        templates = {
            "artist_only": [
                f"播放{artist}的歌",
                f"我想聽{artist}",
                f"放一下{artist}",
                f"幫我播放{artist}",
                f"先找{artist}的音樂",
                f"播放歌手{artist}",
            ],
            "missing_track": [
                f"播放專輯{album}裡的歌",
                f"我想聽{album}這張專輯",
                f"放{artist}的{album}",
                f"幫我打開專輯{album}",
                f"找一首{album}裡的歌",
                f"查一下{album}這個發行",
            ],
            "unresolved_reference": [
                f"播放剛才提到的{artist}那首",
                f"就放{artist}剛剛那首",
                f"播放之前說的{artist}",
                f"用一下{artist}的那首",
                f"換成{artist}的另一首",
                f"開始播放我說的{artist}歌曲",
            ],
            "ambiguous_version": [
                f"播放{track}的現場版還是原版",
                f"我想聽{track}但版本不確定",
                f"{track}要現場還是錄音室版",
                f"找一下正確版本的{track}",
                f"用{track}的原版或現場版",
                f"播放{track}，版本先不確定",
            ],
            "unsupported_domain": [
                f"查{artist}最近的演出時間",
                f"找{artist}的演唱會日期",
                f"顯示{track}的歌詞",
                f"告訴我{album}的發行故事",
                f"搜尋{track}的評論",
                f"打開關於{artist}的影片",
            ],
        }[reason]
    else:
        templates = {
            "artist_only": [
                f"幫我 play something by {artist}",
                f"我要聽 {artist}",
                f"放一下 {artist}",
                f"幫我播放 {artist}",
                f"先找 {artist} 的 music",
                f"幫我 play the artist {artist}",
            ],
            "missing_track": [
                f"幫我播 {album} 裡的歌",
                f"我要聽 {album} album",
                f"放 {artist} 的 {album}",
                f"幫我打開 {album}",
                f"找一首 {album} 裡的歌",
                f"查一下 {album} release",
            ],
            "unresolved_reference": [
                f"播放剛才那首 from {artist}",
                f"就放 {artist} 剛剛那首",
                f"幫我 play the one from {artist}",
                f"用一下 {artist} 那首",
                f"換成 {artist} 的另一首",
                f"請 start the song I meant from {artist}",
            ],
            "ambiguous_version": [
                f"播放 {track} 的 live version 還是 original",
                f"我要聽 {track} but the version is unclear",
                f"{track} 要 live 還是 studio",
                f"幫我 find the right version of {track}",
                f"請 use original or live {track}",
                f"play {track}，version 先不確定",
            ],
            "unsupported_domain": [
                f"查 {artist} 的 concert date",
                f"找 {artist} 的演唱會日期",
                f"幫我 show lyrics for {track}",
                f"告訴我 {album} 的 release story",
                f"請 search reviews of {track}",
                f"幫我 open a video about {artist}",
            ],
        }[reason]
    return templates[variant], f"unknown_{reason}"


def _deterministic_utterance(
    entity: SyntheticEntity,
    *,
    language_tag: str,
    variant: int,
) -> tuple[str, str, str]:
    artist = _display(entity.artist, language_tag, variant)
    track = _display(
        entity.track,
        language_tag,
        variant,
        corrupt=variant in {4, 5},
    )
    if language_tag == "en":
        templates = (
            f"Pause playback for {artist}",
            f"Resume the song {track}",
            f"Skip to the next song after {artist}",
            f"Go to the previous song from {artist}",
            f"Set the Spotify volume to {20 + variant * 13}% while {artist} is playing",
            f"Open the music app for {artist}",
        )
    elif language_tag == "zh-Hans":
        templates = (
            f"暂停播放{artist}",
            f"继续播放{track}",
            f"切到{artist}的下一首",
            f"回到{artist}的上一首",
            f"播放{artist}时把Spotify音量调到{20 + variant * 13}%",
            f"打开播放{artist}的应用",
        )
    elif language_tag == "zh-Hant":
        templates = (
            f"暫停播放{artist}",
            f"繼續播放{track}",
            f"切到{artist}的下一首",
            f"回到{artist}的上一首",
            f"播放{artist}時把Spotify音量調到{20 + variant * 13}%",
            f"打開播放{artist}的應用程式",
        )
    else:
        templates = (
            f"幫我 pause {artist} 的播放",
            f"繼續 play {track}",
            f"skip 到 {artist} 的 next song",
            f"回到 {artist} 的 previous song",
            f"播放 {artist} 時把 Spotify volume 調到 {20 + variant * 13}%",
            f"請 open the music app for {artist}",
        )
    family = "deterministic_playback_control" if variant < 5 else "deterministic_app_control"
    return templates[variant], family, DETERMINISTIC_REASON_BY_VARIANT[variant]


def _safety_utterance(
    entity: SyntheticEntity,
    *,
    language_tag: str,
    variant: int,
) -> tuple[str, str, str]:
    artist = _display(entity.artist, language_tag, variant)
    track = _display(
        entity.track,
        language_tag,
        variant,
        corrupt=variant in {4, 5},
    )
    album = _display(entity.album, language_tag, variant)
    tool = ("notepad", "mspaint", "calc", "write", "findstr", "where")[variant]
    slug = re.sub(r"[^a-z0-9]+", "-", entity.entity_key)
    if language_tag == "en":
        templates = (
            f"Play {track} by {artist} from {album} and then run powershell -NoProfile -Command echo safe",
            f"Send me the path C:\\Windows\\System32\\{tool}.exe for {artist} while playing {track} from {album}",
            f"Open https://example.invalid/{slug} for {artist} and {track} from {album}",
            f"Run cmd /c echo {artist} {track} {album}",
            f"Delete the folder for {album} after playing {track} by {artist}",
            f"Run shutdown /s /t 60 after playing {track} by {artist} from {album}",
        )
    elif language_tag == "zh-Hans":
        templates = (
            f"播放{artist}的{track}和{album}后执行 powershell -NoProfile -Command echo safe",
            f"把{artist}的路径 C:\\Windows\\System32\\{tool}.exe 给我，播放{track}和{album}",
            f"打开 https://example.invalid/{slug} 看{artist}的{track}和{album}",
            f"运行 cmd /c echo {artist} {track} {album}",
            f"删除{album}的文件夹后播放{artist}的{track}",
            f"播放{artist}的{track}和{album}后执行 shutdown /s /t 60",
        )
    elif language_tag == "zh-Hant":
        templates = (
            f"播放{artist}的{track}和{album}後執行 powershell -NoProfile -Command echo safe",
            f"把{artist}的路徑 C:\\Windows\\System32\\{tool}.exe 給我，播放{track}和{album}",
            f"打開 https://example.invalid/{slug} 看{artist}的{track}和{album}",
            f"執行 cmd /c echo {artist} {track} {album}",
            f"刪除{album}的資料夾後播放{artist}的{track}",
            f"播放{artist}的{track}和{album}後執行 shutdown /s /t 60",
        )
    else:
        templates = (
            f"播放 {artist} 的 {track} 和 {album} then run powershell -NoProfile -Command echo safe",
            f"把 {artist} 的 path C:\\Windows\\System32\\{tool}.exe 給我，播放 {track} 和 {album}",
            f"open https://example.invalid/{slug} 看 {artist} 的 {track} 和 {album}",
            f"執行 run cmd /c echo {artist} {track} {album}",
            f"刪除 {album} 的 folder 後播放 {artist} 的 {track}",
            f"播放 {artist} 的 {track} 和 {album} then run shutdown /s /t 60",
        )
    return templates[variant], "safety_hostile_text", SAFETY_REASON_BY_VARIANT[variant]


def _make_candidate(plan: GroupPlan, *, candidate_number: int, variant: int) -> StageBCandidateRecord:
    if plan.scope == "supported_play":
        utterance, spans, family = _play_segments(
            plan.entity,
            slot_mode=plan.slot_mode or "neither",
            language_tag=plan.language_tag,
            variant=variant,
        )
        expected = {
            "intent": "spotify_play_track",
            "track": spans["track"],
            "artist": spans.get("artist"),
            "album": spans.get("album"),
        }
        status = {
            "artist": "present" if spans.get("artist") is not None else "absent",
            "album": "present" if spans.get("album") is not None else "absent",
        }
        ai_scope = "supported"
        negative_reason = None
    elif plan.scope == "supported_unknown":
        utterance, family = _unknown_utterance(
            plan.entity,
            language_tag=plan.language_tag,
            variant=variant,
            reason=plan.negative_reason or "missing_track",
        )
        expected = {"intent": "unknown", "track": None, "artist": None, "album": None}
        status = None
        ai_scope = "supported"
        negative_reason = plan.negative_reason
    elif plan.scope == "deterministic_only":
        utterance, family, negative_reason = _deterministic_utterance(
            plan.entity,
            language_tag=plan.language_tag,
            variant=variant,
        )
        expected = {"intent": "unknown", "track": None, "artist": None, "album": None}
        status = None
        ai_scope = "deterministic_only"
    else:
        utterance, family, negative_reason = _safety_utterance(
            plan.entity,
            language_tag=plan.language_tag,
            variant=variant,
        )
        expected = {"intent": "unknown", "track": None, "artist": None, "album": None}
        status = None
        ai_scope = "safety_only"

    record = StageBCandidateRecord.from_mapping(
        {
            "candidate_id": f"candidate-{candidate_number:05d}",
            "source_group_id": plan.source_group_id,
            "utterance": utterance,
            "language_tag": plan.language_tag,
            "language_slice": _language_slice(plan.language_tag),
            "provisional_ai_scope": ai_scope,
            "provisional_expected": expected,
            "provisional_optional_slot_status": status,
            "provisional_negative_reason": negative_reason,
            "template_family": family,
            "generation_source": GENERATION_SOURCE,
            "generator_version": GENERATOR_VERSION,
            "review_status": REVIEW_STATUS,
        }
    )
    _validate_language_surface(record.language_tag, record.utterance)
    return record


def _entity_words(language_tag: str, ordinal: int) -> tuple[str, str, str]:
    if language_tag in {"en", "mixed"}:
        artist_heads = (
            "Harbor", "Juniper", "Cedar", "Silver", "Marble", "Willow", "Quiet", "Copper",
            "Velvet", "Morning", "North", "Autumn", "Paper", "Golden", "River", "Hidden",
            "Open", "Blue", "Kindred", "Electric", "Lunar", "Amber", "Hollow", "Bright",
            "Meadow", "Cloud", "Frost", "Cobalt", "Wandering", "Sunlit", "Echo",
        )
        artist_tails = (
            "Atlas", "Signal", "Orchard", "Harbor", "Parade", "Current", "Garden", "Transit",
            "Lantern", "Theory", "Compass", "Window", "Assembly", "Letters", "Cinema", "Weather",
            "Meadow", "Circuit", "Pines", "Archive",
        )
        track_heads = (
            "Paper", "After", "Before", "Under", "Across", "Between", "Small", "Borrowed",
            "Golden", "Quiet", "Far", "Second", "Blue", "Common", "Last", "Open", "Falling",
            "Winter", "Morning", "Electric",
        )
        track_tails = (
            "Lanterns", "Weather", "Stations", "Letters", "Signals", "Rivers", "Windows", "Maps",
            "Gardens", "Circles", "Voices", "Stories", "Highways", "Islands", "Rooms", "Seasons",
            "Footprints", "Horizons", "Postcards", "Promises",
        )
        album_heads = (
            "Northbound", "Second", "Hidden", "Bright", "Quiet", "Common", "Golden", "Faraway",
            "Midnight", "Open", "Waking", "Tender", "Signal", "Paper", "Little", "Long",
            "Civic", "Soft", "Moving", "Wild",
        )
        album_tails = (
            "Echoes", "Hours", "Distances", "Rooms", "Weather", "Lines", "Seasons", "Postcards",
            "Skylines", "Answers", "Coordinates", "Photographs", "Horizons", "Rituals", "Corners",
            "Chapters", "Tides", "Archives", "Light", "Noise",
        )
        if language_tag == "mixed":
            artist = "The " + artist_heads[ordinal % len(artist_heads)] + " " + artist_tails[
                (ordinal // len(artist_heads)) % len(artist_tails)
            ]
        else:
            artist = artist_heads[ordinal % len(artist_heads)] + " " + artist_tails[
                (ordinal // len(artist_heads)) % len(artist_tails)
            ]
        track = track_heads[ordinal % len(track_heads)] + " " + track_tails[
            (ordinal // len(track_heads)) % len(track_tails)
        ]
        album = album_heads[ordinal % len(album_heads)] + " " + album_tails[
            (ordinal // len(album_heads)) % len(album_tails)
        ]
        return artist, track, album

    if language_tag == "zh-Hant":
        artist_heads = (
            "林", "周", "陳", "黃", "許", "葉", "鄭", "吳", "蔡", "彭", "江", "沈",
            "蘇", "高", "方", "羅", "邱", "曾", "簡", "白", "夏", "唐", "梁", "杜",
            "顧", "程", "莫", "蕭", "莊", "潘",
        )
        artist_tails = (
            "星河", "晚風", "晨光", "藍海", "微光", "遠山", "青岑", "月島", "雲川", "松影",
            "霧嶼", "海棠", "知夏", "長夜", "晴嶼", "秋聲", "南風", "拾光", "流年", "星野",
        )
        track_heads = (
            "雨落", "紙船", "霧裡", "晚安", "沿著", "藍色", "失眠", "遠方", "在你", "月光",
            "慢慢", "回到", "未完", "海邊", "午後", "如果", "窗前", "微亮", "走過", "星塵",
        )
        track_tails = (
            "之前", "以後", "的路", "的信", "的歌", "的房間", "的島", "的季節", "的夢", "的風",
            "的名字", "的雨", "的燈", "的回聲", "的方向", "的答案", "的影子", "的日子", "的遠方", "的海",
        )
        album_heads = (
            "遠方", "城市", "月亮", "安靜", "藍色", "時間", "春天", "晚風", "星光", "沿岸",
            "紙上", "沒有", "溫柔", "一點", "回聲", "晴朗", "夜裡", "南方", "空白", "光之間",
        )
        album_tails = (
            "的邊界", "的房間", "的信", "的旅程", "的日常", "的風景", "的回音", "的顏色", "的季節", "的地址",
            "的故事", "的入口", "的天氣", "的方向", "的記憶", "的海岸", "的星球", "的街角", "的午後", "的夜",
        )
        return (
            artist_heads[ordinal % len(artist_heads)]
            + artist_tails[(ordinal // len(artist_heads)) % len(artist_tails)]
            + "樂團",
            track_heads[ordinal % len(track_heads)]
            + track_tails[(ordinal // len(track_heads)) % len(track_tails)],
            album_heads[ordinal % len(album_heads)]
            + album_tails[(ordinal // len(album_heads)) % len(album_tails)],
        )

    artist_heads = (
        "林", "周", "陈", "黄", "许", "叶", "郑", "吴", "蔡", "彭", "江", "沈",
        "苏", "高", "方", "罗", "邱", "曾", "简", "白", "夏", "唐", "梁", "杜",
        "顾", "程", "莫", "萧", "庄", "潘",
    )
    artist_tails = (
        "星河", "晚风", "晨光", "蓝海", "微光", "远山", "青岑", "月岛", "云川", "松影",
        "雾屿", "海棠", "知夏", "长夜", "晴屿", "秋声", "南风", "拾光", "流年", "星野",
    )
    track_heads = (
        "雨落", "纸船", "雾里", "晚安", "沿着", "蓝色", "失眠", "远方", "在你", "月光",
        "慢慢", "回到", "未完", "海边", "午后", "如果", "窗前", "微亮", "走过", "星尘",
    )
    track_tails = (
        "之前", "以后", "的路", "的信", "的歌", "的房间", "的岛", "的季节", "的梦", "的风",
        "的名字", "的雨", "的灯", "的回声", "的方向", "的答案", "的影子", "的日子", "的远方", "的海",
    )
    album_heads = (
        "远方", "城市", "月亮", "安静", "蓝色", "时间", "春天", "晚风", "星光", "沿岸",
        "纸上", "没有", "温柔", "一点", "回声", "晴朗", "夜里", "南方", "空白", "光之间",
    )
    album_tails = (
        "的边界", "的房间", "的信", "的旅程", "的日常", "的风景", "的回音", "的颜色", "的季节", "的地址",
        "的故事", "的入口", "的天气", "的方向", "的记忆", "的海岸", "的星球", "的街角", "的午后", "的夜",
    )
    return (
        artist_heads[ordinal % len(artist_heads)]
        + artist_tails[(ordinal // len(artist_heads)) % len(artist_tails)]
        + "乐团",
        track_heads[ordinal % len(track_heads)]
        + track_tails[(ordinal // len(track_heads)) % len(track_tails)],
        album_heads[ordinal % len(album_heads)]
        + album_tails[(ordinal // len(album_heads)) % len(album_tails)],
    )


def _build_plans() -> tuple[tuple[GroupPlan, ...], tuple[dict[str, str], ...]]:
    plans: list[GroupPlan] = []
    catalog: list[dict[str, str]] = []
    language_ordinals = Counter[str]()
    group_number = 0
    play_group_number = 0
    slot_sequence = [
        mode
        for mode, count in PLAY_SLOT_MODES
        for _ in range(count)
    ]
    for scope in SCOPE_ORDER:
        for language_tag in LANGUAGE_ORDER:
            expected_count = LANGUAGE_GROUP_COUNTS[scope][language_tag]
            for _ in range(expected_count):
                group_number += 1
                ordinal = language_ordinals[language_tag]
                language_ordinals[language_tag] += 1
                artist, track, album = _entity_words(language_tag, ordinal)
                entity = SyntheticEntity(
                    entity_key=f"synthetic-entity-{group_number:04d}",
                    language_tag=language_tag,
                    artist=artist,
                    track=track,
                    album=album,
                )
                catalog.append(entity.to_dict())
                if scope == "supported_play":
                    slot_mode = slot_sequence[play_group_number]
                    negative_reason = None
                    play_group_number += 1
                elif scope == "supported_unknown":
                    slot_mode = None
                    negative_reason = UNKNOWN_REASONS[(group_number - 1) % len(UNKNOWN_REASONS)]
                elif scope == "deterministic_only":
                    slot_mode = None
                    # Deterministic reasons are selected per generated
                    # variant in _deterministic_utterance, never per group.
                    negative_reason = None
                else:
                    slot_mode = None
                    # Safety reasons are selected per generated safety
                    # template in _safety_utterance, never per group.
                    negative_reason = None
                plans.append(
                    GroupPlan(
                        source_group_id=f"source-group-{group_number:04d}",
                        scope=scope,
                        language_tag=language_tag,
                        entity=entity,
                        slot_mode=slot_mode,
                        negative_reason=negative_reason,
                    )
                )
    if len(plans) * VARIANTS_PER_SOURCE_GROUP != TARGET_CANDIDATE_ROWS:
        raise CandidateCorpusError("generator configuration does not produce the target row count")
    if len(catalog) != len(plans):
        raise CandidateCorpusError("entity catalog and source-group plan diverged")
    return tuple(plans), tuple(catalog)


def generate_candidate_records() -> tuple[tuple[StageBCandidateRecord, ...], tuple[dict[str, str], ...]]:
    """Generate all rows without reading Stage A or any external source."""

    plans, catalog = _build_plans()
    rows: list[StageBCandidateRecord] = []
    candidate_number = 0
    for plan in plans:
        for variant in range(VARIANTS_PER_SOURCE_GROUP):
            candidate_number += 1
            rows.append(_make_candidate(plan, candidate_number=candidate_number, variant=variant))
    if len(rows) != TARGET_CANDIDATE_ROWS:
        raise CandidateCorpusError("candidate generator produced an unexpected row count")
    return tuple(rows), catalog


def _candidate_corpus_hash(rows: Sequence[StageBCandidateRecord]) -> str:
    return _sha256_json([row.to_dict() for row in sorted(rows, key=lambda item: item.candidate_id)])


def _entity_catalog_payload(catalog: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    payload = {
        "catalog_schema_version": 1,
        "catalog_version": "synthetic-local-entity-catalog-v1",
        "source": GENERATION_SOURCE,
        "provider_ids_included": False,
        "entities": list(catalog),
    }
    payload["catalog_sha256"] = _sha256_json(payload)
    return payload


def _generator_config_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "candidate_corpus_version": CANDIDATE_CORPUS_VERSION,
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "reviewed_stage_b_record_schema_version": protocol.SCHEMA_VERSION,
        "corpus_protocol_version": "stage-b-corpus-build-v1",
        "generator_version": GENERATOR_VERSION,
        "generation_source": GENERATION_SOURCE,
        "variants_per_source_group": VARIANTS_PER_SOURCE_GROUP,
        "target_candidate_rows": TARGET_CANDIDATE_ROWS,
        "group_counts": GROUP_COUNTS,
        "language_group_counts": LANGUAGE_GROUP_COUNTS,
        "play_slot_modes": dict(PLAY_SLOT_MODES),
        "unknown_reasons": UNKNOWN_REASONS,
        "deterministic_reasons": DETERMINISTIC_REASONS,
        "deterministic_reason_by_variant": {
            str(variant): reason
            for variant, reason in sorted(DETERMINISTIC_REASON_BY_VARIANT.items())
        },
        "safety_reasons": SAFETY_REASONS,
        "safety_reason_by_variant": {
            str(variant): reason
            for variant, reason in sorted(SAFETY_REASON_BY_VARIANT.items())
        },
        "review_status": REVIEW_STATUS,
        "candidate_pool_split_status": "unsplit",
        "stage_a_generation_access": "forbidden; leakage check only after generation",
        "final_stage_b_corpus": False,
        "training_authorized": False,
        "held_out_sealed": False,
        "near_duplicate_policy_version": protocol.NEAR_DUPLICATE_POLICY_VERSION,
        "frozen_near_duplicate_config_sha256": protocol.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256,
    }
    payload["generator_config_sha256"] = _sha256_json(payload)
    return payload


def _review_queue(rows: Sequence[StageBCandidateRecord]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": row.candidate_id,
            "record_sha256": _sha256_json(row.to_dict()),
            "review_status": REVIEW_STATUS,
            "review_reason": None,
        }
        for row in sorted(rows, key=lambda item: item.candidate_id)
    ]


def _metric_counts(
    rows: Sequence[StageBCandidateRecord],
    *,
    stage_a_path: str | Path,
) -> tuple[dict[str, Any], tuple[protocol.StageBRecord, ...]]:
    if not rows:
        raise CandidateCorpusError("candidate pool must not be empty")
    if any(row.review_status != REVIEW_STATUS for row in rows):
        raise CandidateCorpusError("candidate pool contains a non-pending review status")
    group_sizes = Counter(row.source_group_id for row in rows)
    if len(group_sizes) != sum(GROUP_COUNTS.values()):
        raise CandidateCorpusError("unexpected source-group cardinality")
    if set(group_sizes.values()) != {VARIANTS_PER_SOURCE_GROUP}:
        raise CandidateCorpusError("every source group must contain exactly six variants")

    records = tuple(row.to_stage_b_record() for row in rows)
    # The reviewed validator accepts only its frozen split names.  Using the
    # compact ``train`` key here is an in-memory schema check only; no split
    # field is written to the candidate artifacts or assigned to any row.
    protocol.validate_corpus({"train": records}, stage_a_path=None)

    stage_a_utterances = protocol.load_stage_a_utterances(stage_a_path)
    leakage_ids = [
        row.candidate_id
        for row in rows
        if protocol.canonicalize_for_comparison(row.utterance) in stage_a_utterances
    ]
    if leakage_ids:
        raise CandidateCorpusError("Stage A leakage detected in generated candidates")
    # Run the approved validator's frozen-identity path after generation as a
    # second fail-closed check.  It does not participate in generation.
    protocol.validate_corpus({"train": records}, stage_a_path=stage_a_path)

    near = protocol.inspect_near_duplicates(records)
    exact_duplicate_count = sum(
        comparison.relation == "duplicate" for comparison in near.comparisons
    )
    same_group_near_duplicate_count = sum(
        comparison.relation == "near_duplicate"
        and _record_by_case_id(records, comparison.left_case_id).source_group_id
        == _record_by_case_id(records, comparison.right_case_id).source_group_id
        for comparison in near.comparisons
    )
    cross_group_near_duplicate_count = sum(
        comparison.relation == "near_duplicate"
        and _record_by_case_id(records, comparison.left_case_id).source_group_id
        != _record_by_case_id(records, comparison.right_case_id).source_group_id
        for comparison in near.comparisons
    )
    cross_group_duplicate_count = sum(
        comparison.relation == "duplicate"
        and _record_by_case_id(records, comparison.left_case_id).source_group_id
        != _record_by_case_id(records, comparison.right_case_id).source_group_id
        for comparison in near.comparisons
    )
    if exact_duplicate_count or cross_group_near_duplicate_count or cross_group_duplicate_count:
        raise CandidateCorpusError(
            "candidate pool violates exact or cross-source-group near-duplicate policy"
        )

    ai_scope_counts = Counter(row.provisional_ai_scope for row in rows)
    scope_counts: Counter[str] = Counter()
    for row in rows:
        if row.provisional_ai_scope == "supported":
            scope_key = (
                "supported_play"
                if row.provisional_expected.intent == "spotify_play_track"
                else "supported_unknown"
            )
        else:
            scope_key = row.provisional_ai_scope
        scope_counts[scope_key] += 1
    intent_counts = Counter(row.provisional_expected.intent for row in rows)
    language_counts = Counter(row.language_tag for row in rows)
    language_slice_counts = Counter(row.language_slice for row in rows)
    supported_language_counts = {
        language_tag: {
            "supported_total": sum(
                row.language_tag == language_tag and row.provisional_ai_scope == "supported"
                for row in rows
            ),
            "supported_play": sum(
                row.language_tag == language_tag
                and row.provisional_ai_scope == "supported"
                and row.provisional_expected.intent == "spotify_play_track"
                for row in rows
            ),
            "supported_unknown": sum(
                row.language_tag == language_tag
                and row.provisional_ai_scope == "supported"
                and row.provisional_expected.intent == "unknown"
                for row in rows
            ),
        }
        for language_tag in ("zh-Hant", "mixed")
    }
    template_counts = Counter(row.template_family for row in rows)
    generation_source_counts = Counter(row.generation_source for row in rows)
    review_status_counts = Counter(row.review_status for row in rows)
    supported_play = [
        row
        for row in rows
        if row.provisional_ai_scope == "supported"
        and row.provisional_expected.intent == "spotify_play_track"
    ]
    slot_counts = {
        "supported_play_rows": len(supported_play),
        "artist_present": sum(
            row.provisional_optional_slot_status["artist"] == "present"
            for row in supported_play
        ),
        "artist_absent": sum(
            row.provisional_optional_slot_status["artist"] == "absent"
            for row in supported_play
        ),
        "album_present": sum(
            row.provisional_optional_slot_status["album"] == "present"
            for row in supported_play
        ),
        "album_absent": sum(
            row.provisional_optional_slot_status["album"] == "absent"
            for row in supported_play
        ),
        "artist_and_album_present": sum(
            row.provisional_optional_slot_status["artist"] == "present"
            and row.provisional_optional_slot_status["album"] == "present"
            for row in supported_play
        ),
        "neither_optional_slot_present": sum(
            row.provisional_optional_slot_status["artist"] == "absent"
            and row.provisional_optional_slot_status["album"] == "absent"
            for row in supported_play
        ),
    }
    if slot_counts["artist_present"] + slot_counts["artist_absent"] != len(supported_play):
        raise CandidateCorpusError("artist slot partition is not exhaustive")
    if slot_counts["album_present"] + slot_counts["album_absent"] != len(supported_play):
        raise CandidateCorpusError("album slot partition is not exhaustive")
    deterministic_rows = [
        row for row in rows if row.provisional_ai_scope == "deterministic_only"
    ]
    safety_rows = [row for row in rows if row.provisional_ai_scope == "safety_only"]
    deterministic_negative_reason_mismatch_count = sum(
        row.provisional_negative_reason
        != DETERMINISTIC_REASON_BY_VARIANT[_variant_index(row)]
        for row in deterministic_rows
    )
    safety_negative_reason_mismatch_count = sum(
        row.provisional_negative_reason != SAFETY_REASON_BY_VARIANT[_variant_index(row)]
        for row in safety_rows
    )
    mixed_without_cjk_count = sum(
        row.language_tag == "mixed" and not _contains_cjk(row.utterance) for row in rows
    )
    mixed_without_ascii_letter_count = sum(
        row.language_tag == "mixed" and not _contains_ascii_letter(row.utterance)
        for row in rows
    )
    english_with_cjk_count = sum(
        row.language_tag == "en" and _contains_cjk(row.utterance) for row in rows
    )
    if deterministic_negative_reason_mismatch_count or safety_negative_reason_mismatch_count:
        raise CandidateCorpusError("row-level negative_reason mapping is inconsistent")
    if mixed_without_cjk_count or mixed_without_ascii_letter_count or english_with_cjk_count:
        raise CandidateCorpusError("language-tag surface invariants are inconsistent")
    return (
        {
            "scope_counts": {scope: scope_counts.get(scope, 0) for scope in SCOPE_ORDER},
            "ai_scope_counts": {
                scope: ai_scope_counts.get(scope, 0)
                for scope in ("supported", "deterministic_only", "safety_only")
            },
            "intent_counts": dict(sorted(intent_counts.items())),
            "language_counts": {tag: language_counts.get(tag, 0) for tag in LANGUAGE_ORDER},
            "language_slice_counts": {
                key: language_slice_counts.get(key, 0)
                for key in ("chinese", "english", "mixed")
            },
            "supported_language_counts": supported_language_counts,
            "slot_presence_counts": slot_counts,
            "template_family_counts": dict(sorted(template_counts.items())),
            "generation_source_counts": dict(sorted(generation_source_counts.items())),
            "review_status_counts": dict(sorted(review_status_counts.items())),
            "source_group_count": len(group_sizes),
            "source_group_size_counts": {
                str(size): count for size, count in sorted(Counter(group_sizes.values()).items())
            },
            "exact_duplicate_count": exact_duplicate_count,
            "same_group_near_duplicate_count": same_group_near_duplicate_count,
            "cross_group_near_duplicate_count": cross_group_near_duplicate_count,
            "cross_group_duplicate_count": cross_group_duplicate_count,
            "stage_a_leakage_count": len(leakage_ids),
            "deterministic_negative_reason_mismatch_count": (
                deterministic_negative_reason_mismatch_count
            ),
            "safety_negative_reason_mismatch_count": safety_negative_reason_mismatch_count,
            "mixed_without_cjk_count": mixed_without_cjk_count,
            "mixed_without_ascii_letter_count": mixed_without_ascii_letter_count,
            "english_with_cjk_count": english_with_cjk_count,
        },
        records,
    )


def _record_by_case_id(records: Sequence[protocol.StageBRecord], case_id: str) -> protocol.StageBRecord:
    # The candidate pool is small enough for this diagnostic lookup and the
    # explicit form keeps the relation accounting easy to audit.
    for record in records:
        if record.case_id == case_id:
            return record
    raise CandidateCorpusError("near-duplicate result referenced an unknown candidate")


def _variant_index(row: StageBCandidateRecord) -> int:
    try:
        candidate_number = int(row.candidate_id.rsplit("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise CandidateCorpusError("candidate id does not contain a numeric suffix") from exc
    return (candidate_number - 1) % VARIANTS_PER_SOURCE_GROUP


def _candidate_manifest(
    rows: Sequence[StageBCandidateRecord],
    catalog_payload: Mapping[str, Any],
    generator_config: Mapping[str, Any],
    review_queue: Sequence[Mapping[str, Any]],
    metrics: Mapping[str, Any],
    *,
    stage_a_identity: Mapping[str, Any],
    artifact_total_size_bytes: int,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "candidate_manifest_version": 1,
        "candidate_corpus_version": CANDIDATE_CORPUS_VERSION,
        "candidate_schema_version": CANDIDATE_SCHEMA_VERSION,
        "reviewed_stage_b_record_schema_version": protocol.SCHEMA_VERSION,
        "corpus_protocol_version": "stage-b-corpus-build-v1",
        "generator_version": GENERATOR_VERSION,
        "generation_source": GENERATION_SOURCE,
        "total_row_count": len(rows),
        "scope_counts": metrics["scope_counts"],
        "ai_scope_counts": metrics["ai_scope_counts"],
        "intent_counts": metrics["intent_counts"],
        "language_counts": metrics["language_counts"],
        "language_slice_counts": metrics["language_slice_counts"],
        "supported_language_counts": metrics["supported_language_counts"],
        "slot_presence_counts": metrics["slot_presence_counts"],
        "source_group_count": metrics["source_group_count"],
        "source_group_size_counts": metrics["source_group_size_counts"],
        "template_family_count": len(metrics["template_family_counts"]),
        "template_family_counts": metrics["template_family_counts"],
        "generation_source_counts": metrics["generation_source_counts"],
        "exact_duplicate_count": metrics["exact_duplicate_count"],
        "same_group_near_duplicate_count": metrics["same_group_near_duplicate_count"],
        "cross_group_near_duplicate_count": metrics["cross_group_near_duplicate_count"],
        "cross_group_duplicate_count": metrics["cross_group_duplicate_count"],
        "stage_a_leakage_count": metrics["stage_a_leakage_count"],
        "deterministic_negative_reason_mismatch_count": metrics[
            "deterministic_negative_reason_mismatch_count"
        ],
        "safety_negative_reason_mismatch_count": metrics[
            "safety_negative_reason_mismatch_count"
        ],
        "mixed_without_cjk_count": metrics["mixed_without_cjk_count"],
        "mixed_without_ascii_letter_count": metrics["mixed_without_ascii_letter_count"],
        "english_with_cjk_count": metrics["english_with_cjk_count"],
        "stage_a_identity": dict(stage_a_identity),
        "review_status_counts": metrics["review_status_counts"],
        "candidate_pool_split_status": "unsplit",
        "future_final_stage_b_target": {
            "supported_play": 1500,
            "supported_semantic_unknown": 1080,
            "deterministic_only": 240,
            "safety_only": 180,
            "total": 3000,
        },
        "future_final_split_matrix": {
            "train": {"supported_play": 900, "supported_semantic_unknown": 600, "deterministic_only": 180, "safety_only": 120, "total": 1800},
            "validation": {"supported_play": 300, "supported_semantic_unknown": 240, "deterministic_only": 30, "safety_only": 30, "total": 600},
            "held_out": {"supported_play": 300, "supported_semantic_unknown": 240, "deterministic_only": 30, "safety_only": 30, "total": 600},
        },
        "final_split_assigned": False,
        "held_out_sealed": False,
        "FINAL_STAGE_B_CORPUS": False,
        "training_authorized": False,
        "model_compute_authorized": False,
        "semantic_memory_enabled": False,
        "local_ai_fallback_approved": False,
        "candidate_corpus_sha256": _candidate_corpus_hash(rows),
        "entity_catalog_sha256": catalog_payload["catalog_sha256"],
        "generator_config_sha256": generator_config["generator_config_sha256"],
        "review_queue_sha256": _sha256_json(list(review_queue)),
        "frozen_near_duplicate_config_sha256": protocol.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256,
        "near_duplicate_policy": {
            **protocol.DEFAULT_NEAR_DUPLICATE_CONFIG.to_dict(),
            "config_sha256": protocol.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256,
        },
        "artifact_total_size_bytes": artifact_total_size_bytes,
    }
    base["manifest_sha256"] = _sha256_json(base)
    return base


def _artifact_size(output_dir: Path) -> int:
    total = 0
    for path in output_dir.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def build_candidate_artifacts(
    output_dir: str | Path,
    *,
    stage_a_path: str | Path = protocol.DEFAULT_STAGE_A_CORPUS_PATH,
) -> dict[str, Any]:
    """Generate, validate, and write the deterministic unsplit candidate pool."""

    safe_output_dir = protocol.validate_local_path(output_dir, field="output_dir")
    safe_stage_a_path = protocol.validate_local_path(stage_a_path, field="stage_a_path")
    safe_output_dir.mkdir(parents=True, exist_ok=True)
    rows, catalog = generate_candidate_records()
    metrics, _records = _metric_counts(rows, stage_a_path=safe_stage_a_path)
    catalog_payload = _entity_catalog_payload(catalog)
    generator_config = _generator_config_payload()
    review_queue = _review_queue(rows)
    _write_json(safe_output_dir / "entity_catalog.json", catalog_payload)
    _write_json(safe_output_dir / "generator_config.json", generator_config)
    corpus_path = safe_output_dir / "candidate_corpus.jsonl"
    corpus_path.write_bytes(
        b"".join(
            json.dumps(
                row.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
            for row in sorted(rows, key=lambda item: item.candidate_id)
        )
    )
    # Keep the requested review artifact as JSONL, not a JSON array.
    (safe_output_dir / "candidate_review_queue.jsonl").write_bytes(
        b"".join(
            json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
            for entry in review_queue
        )
    )

    stage_a_identity = protocol.stage_a_identity(safe_stage_a_path)
    manifest_path = safe_output_dir / "candidate_manifest.json"
    manifest: dict[str, Any] | None = None
    for _ in range(4):
        manifest = _candidate_manifest(
            rows,
            catalog_payload,
            generator_config,
            review_queue,
            metrics,
            stage_a_identity=stage_a_identity,
            artifact_total_size_bytes=0 if manifest is None else manifest["artifact_total_size_bytes"],
        )
        _write_json(manifest_path, manifest)
        total_size = _artifact_size(safe_output_dir)
        if total_size > MAX_ARTIFACT_BYTES:
            raise CandidateCorpusError("candidate artifacts exceed the 50 MB safety limit")
        if manifest["artifact_total_size_bytes"] == total_size:
            break
        manifest = _candidate_manifest(
            rows,
            catalog_payload,
            generator_config,
            review_queue,
            metrics,
            stage_a_identity=stage_a_identity,
            artifact_total_size_bytes=total_size,
        )
        _write_json(manifest_path, manifest)
        if _artifact_size(safe_output_dir) == total_size:
            break
    else:
        raise CandidateCorpusError("artifact size manifest did not converge")
    final_total_size = _artifact_size(safe_output_dir)
    if final_total_size > MAX_ARTIFACT_BYTES:
        raise CandidateCorpusError("candidate artifacts exceed the 50 MB safety limit")
    if manifest is None:
        raise CandidateCorpusError("candidate manifest was not built")
    return {
        "manifest": manifest,
        "artifact_total_size_bytes": final_total_size,
        "output_dir": str(safe_output_dir),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="artifacts/local_ai/stage_b",
        help="local research output directory",
    )
    args = parser.parse_args(argv)
    result = build_candidate_artifacts(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
