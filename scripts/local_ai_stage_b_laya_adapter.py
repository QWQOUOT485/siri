"""Research-only Laya shape adapter. No production import or execution authority."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "local_ai_stage_b_laya_shape_smoke_v1.jsonl"
QUESTION = {"t": "choice", "ins": "Classify the music request.", "crit": {"play": None, "unknown": None}}
LIVE_IDS = tuple(f"smoke-{n:03d}" for n in (1, 9, 17, 25, 33, 41, 49, 57))
FIELDS = {"row_id", "language", "utterance", "expected_intent", "track_span", "artist_span", "album_span"}
SLOT_TAGS = {"track_span": (1, 2), "artist_span": (3, 4), "album_span": (5, 6)}
FORBIDDEN_TEXT = re.compile(r"https?://|spotify:|[a-zA-Z]:[\\/]|\\\\|\b(?:cmd|powershell|shutdown|delete)\b", re.I)


class ShapeError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ShapeError(message)


def load_fixture(path: Path = FIXTURE) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    require(len(rows) == 64, "fixture_row_count")
    for n, row in enumerate(rows, 1):
        require(isinstance(row, dict) and set(row) == FIELDS, "fixture_fields")
        require(row["row_id"] == f"smoke-{n:03d}", "fixture_id_or_order")
        expected_language = "zh-Hant" if n <= 8 or 33 <= n <= 40 or 57 <= n <= 64 else "en" if 9 <= n <= 16 or 41 <= n <= 48 else "mixed"
        expected_intent = "play" if n <= 32 else "unknown"
        require(row["language"] == expected_language and row["expected_intent"] == expected_intent,
                "fixture_slice")
        utterance = row["utterance"]
        require(isinstance(utterance, str) and 0 < len(utterance) <= 120
                and not FORBIDDEN_TEXT.search(utterance), "fixture_utterance")
        spans = []
        for field in SLOT_TAGS:
            span = row[field]
            if span is None:
                continue
            require(isinstance(span, dict) and set(span) == {"start", "end"}
                    and type(span["start"]) is int and type(span["end"]) is int
                    and 0 <= span["start"] < span["end"] <= len(utterance)
                    and utterance[span["start"]:span["end"]].strip(), "fixture_span")
            spans.append((span["start"], span["end"]))
        spans.sort()
        require(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), "fixture_span_overlap")
        require((row["track_span"] is not None) == (expected_intent == "play"), "fixture_track_presence")
        require(expected_intent == "play" or not spans, "fixture_unknown_slots")
        require(n > 16 or row["artist_span"] is None, "fixture_artist_slice")
        require(n > 24 or row["album_span"] is None, "fixture_album_slice")
        require(n <= 32 or row["artist_span"] is None and row["album_span"] is None,
                "fixture_unknown_slots")
        require(n < 17 or n > 32 or row["artist_span"] is not None, "fixture_artist_slice")
        require(n < 25 or n > 32 or row["album_span"] is not None, "fixture_album_slice")
    return rows


def render_row(tok: Any, row: dict[str, Any], *, max_len: int = 512,
               head_max_len: int = 192) -> dict[str, Any]:
    """Mirror pinned build_sequence for one fixed choice and retain state offsets."""
    ins = QUESTION["ins"].replace(tok.mask_token, " ")
    head = tok("choice question: " + ins, add_special_tokens=False)["input_ids"]
    options = [[tok.mask_token_id] + tok(" " + option, add_special_tokens=False)["input_ids"][:48]
               for option in ("play", "unknown")]
    budget = head_max_len - sum(map(len, options))
    if budget < 16:
        per = max(4, (head_max_len - 16) // len(options))
        options = [option[:per] for option in options]
        budget = head_max_len - sum(map(len, options))
    head = head[:max(8, budget)]
    ids = [tok.cls_token_id] + head + [tok.sep_token_id]
    markers = []
    for option in options:
        markers.append(len(ids))
        ids.extend(option)
    ids.append(tok.sep_token_id)
    encoded = tok(row["utterance"].replace(tok.mask_token, " "),
                  add_special_tokens=False, return_offsets_mapping=True)
    state_ids = encoded["input_ids"]
    offsets = [tuple(pair) for pair in encoded["offset_mapping"]]
    require(len(state_ids) == len(offsets) and len(state_ids) <= max_len - len(ids) - 1,
            "required_state_truncated")
    require(not set(state_ids) & {tok.cls_token_id, tok.sep_token_id, tok.mask_token_id, tok.pad_token_id},
            "special_token_in_state")
    start = len(ids)
    ids.extend(state_ids)
    ids.append(tok.sep_token_id)
    mask = [False] * len(ids)
    labels = [-100] * len(ids)
    token_offsets: list[tuple[int, int] | None] = [None] * len(ids)
    for j, (a, b) in enumerate(offsets, start):
        require(0 <= a < b <= len(row["utterance"]), "state_token_offset")
        mask[j] = True
        labels[j] = 0
        token_offsets[j] = (a, b)
    for field, (begin, inside) in SLOT_TAGS.items():
        span = row[field]
        if span is None:
            continue
        covered = [j for j in range(start, start + len(offsets))
                   if offsets[j - start][0] < span["end"] and offsets[j - start][1] > span["start"]]
        require(bool(covered) and all(mask[j] and labels[j] == 0 for j in covered),
                "slot_token_mapping")
        labels[covered[0]] = begin
        for j in covered[1:]:
            labels[j] = inside
    require(row["expected_intent"] != "play" or 1 in labels, "track_token_missing")
    require(row["expected_intent"] != "unknown" or all(label in (-100, 0) for label in labels),
            "unknown_non_o_label")
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "marker_pos": markers,
            "marker_mask": [True, True], "qtype": 0, "user_state_mask": mask,
            "token_offsets": token_offsets, "bio_labels": labels,
            "intent_label": 0 if row["expected_intent"] == "play" else 1,
            "validity_label": 1 if row["expected_intent"] == "play" else 0}


def validate_rendering(tok: Any, build_sequence: Any, rows: list[dict[str, Any]],
                       *, max_len: int = 512, head_max_len: int = 192) -> list[dict[str, Any]]:
    rendered = []
    for row in rows:
        item = render_row(tok, row, max_len=max_len, head_max_len=head_max_len)
        upstream_ids, upstream_markers = build_sequence(tok, row["utterance"], QUESTION,
                                                        max_len, head_max_len)
        require(item["input_ids"] == upstream_ids and item["marker_pos"] == upstream_markers,
                "STOP_LAYA_RENDERING_DIVERGENCE")
        require(item == render_row(tok, row, max_len=max_len, head_max_len=head_max_len),
                "render_nondeterministic")
        rendered.append(item)
    return rendered


def safe_slots(intent: str, utterance: str, spans: dict[str, dict[str, int] | None]) -> dict[str, Any]:
    null = {"intent": "unknown", "track": None, "artist": None, "album": None}
    if intent != "play":
        return null
    result: dict[str, Any] = {"intent": "play"}
    for name in ("track", "artist", "album"):
        span = spans.get(name)
        valid = isinstance(span, dict) and set(span) == {"start", "end"} and all(
            type(span[key]) is int for key in ("start", "end")) and 0 <= span["start"] < span["end"] <= len(utterance)
        result[name] = utterance[span["start"]:span["end"]] if valid else None
    return result if result["track"] and result["track"].strip() else null
