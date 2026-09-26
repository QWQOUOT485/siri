"""Reusable reviewed S3 decoder. Not activated in app or historical research runners."""
from __future__ import annotations

import math
from typing import Any

import local_ai_stage_b_laya_adapter as adapter

SLOTS = ('track', 'artist', 'album')
NULL = {'intent': 'unknown', **dict.fromkeys(SLOTS)}


def owner(tag: int) -> str:
    return SLOTS[(tag - 1) // 2] if tag in range(1, 7) else 'O'


def valid_pair(pair: Any, length: int) -> bool:
    return (isinstance(pair, (tuple, list)) and len(pair) == 2
            and all(type(v) is int for v in pair) and 0 <= pair[0] < pair[1] <= length)


def tighten(text: str, span: Any) -> Any:
    if span is None:
        return None
    a, b = span['start'], span['end']
    if not valid_pair((a, b), len(text)):
        return None
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return {'start': a, 'end': b} if a < b else None


def finish(spans: dict[str, Any], text: str) -> dict[str, Any]:
    result = {}
    for slot in SLOTS:
        span = tighten(text, spans[slot])
        if span is not None:
            value = text[span['start']:span['end']]
            if not value.strip() or adapter.FORBIDDEN_TEXT.search(value):
                span = None
        result[slot] = span
    return {'intent': 'play', **result} if result['track'] is not None else dict(NULL)


def decode(typed_index: int, validity_probability: float, labels: list[int],
           mask: list[bool], offsets: list[Any], text: str) -> dict[str, Any]:
    """Decode reviewed S3 raw spans; no execution/provider authority or offset repair."""
    if (type(typed_index) is not int or typed_index not in (0, 1) or typed_index != 0
            or type(validity_probability) not in (int, float)
            or not 0.5 <= validity_probability <= 1 or not math.isfinite(validity_probability)):
        return dict(NULL)
    if (not isinstance(text, str) or not all(isinstance(v, (list, tuple)) for v in (labels, mask, offsets))
            or any(type(v) is not bool for v in mask)):
        return dict(NULL)
    if not len(labels) == len(mask) == len(offsets) or any(type(t) is not int or t not in range(7) for t in labels):
        return dict(NULL)
    invalid = set()
    indices = {slot: [] for slot in SLOTS}
    for i, (tag, inside, pair) in enumerate(zip(labels, mask, offsets)):
        slot = owner(tag)
        if not inside:
            if tag or pair is not None:
                return dict(NULL)
            continue
        if not valid_pair(pair, len(text)):
            if slot == 'O':
                return dict(NULL)
            invalid.add(slot)
        if tag:
            indices[slot].append(i)
    # Conflicts/order reversals involving selected tokens fail their owners.
    # Unselected O/O overlaps cannot change a slot's raw boundaries.
    user = [i for i, inside in enumerate(mask) if inside and valid_pair(offsets[i], len(text))]
    for pos, i in enumerate(user):
        for j in user[pos + 1:]:
            if (owner(labels[i]) == owner(labels[j]) == 'O'
                    and (offsets[j][0] < offsets[i][0] or offsets[j][1] < offsets[i][1])):
                return dict(NULL)
            if offsets[j][0] < offsets[i][1]:
                invalid.update(s for s in (owner(labels[i]), owner(labels[j])) if s != 'O')
    spans = dict.fromkeys(SLOTS)
    for slot, ids in indices.items():
        if not ids or slot in invalid:
            continue
        begin, inner = adapter.SLOT_TAGS[slot + '_span']
        if (labels[ids[0]] != begin or any(labels[i] != inner for i in ids[1:])
                or ids != list(range(ids[0], ids[-1] + 1))):
            continue
        first, last = offsets[ids[0]], offsets[ids[-1]]
        a, b = first[0], last[1]
        spans[slot] = {'start': a, 'end': b}
    return finish(spans, text)
