"""Design-only gold-label oracle simulations; never imported by runtime code."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import local_ai_stage_b_laya_span_representability_audit as audit

BASE = 'a69e96284280eaf2aa2b9b59b70814520edeb51d'
PR81_HASH = '1785052a43f1e20662ce27da9d57d857b3ff132af156afc3d7f7cebf602de2f5'
DENOMS = {'train': {'track': 900, 'artist': 612, 'album': 582},
          'validation': {'track': 300, 'artist': 126, 'album': 204}}
GATES = {'track': 285, 'artist': 120, 'album': 194}
SLOTS = audit.SLOTS
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


def finish(spans: dict[str, Any], text: str, trim: bool) -> dict[str, Any]:
    result = {}
    for slot in SLOTS:
        span = tighten(text, spans[slot]) if trim else spans[slot]
        if span is not None:
            value = text[span['start']:span['end']]
            if not value.strip() or audit.adapter.FORBIDDEN_TEXT.search(value):
                span = None
        result[slot] = span
    return {'intent': 'play', **result} if result['track'] is not None else dict(NULL)


def isolated(labels: list[int], mask: list[bool], offsets: list[Any], text: str,
             *, trim: bool = False, residuals: dict[str, Any] | None = None) -> dict[str, Any]:
    """Simulation only: reject each affected slot, with no offset-order repair."""
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
        begin, inner = audit.adapter.SLOT_TAGS[slot + '_span']
        if (labels[ids[0]] != begin or any(labels[i] != inner for i in ids[1:])
                or ids != list(range(ids[0], ids[-1] + 1))):
            continue
        first, last = offsets[ids[0]], offsets[ids[-1]]
        a, b = first[0], last[1]
        if residuals is not None:
            pair = residuals.get(slot)
            if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                    or any(type(v) is not int for v in pair)):
                continue
            left, right = pair
            if not (0 <= left < first[1] - first[0] and 0 <= right < last[1] - last[0]):
                continue
            a, b = first[0] + left, last[1] - right
            if a >= b:
                continue
        spans[slot] = {'start': a, 'end': b}
    return finish(spans, text, trim)


def current_rejection(labels: list[int], mask: list[bool], offsets: list[Any], text: str) -> dict[str, Any]:
    """Trace the current decoder's precise first row rejection, without changing it."""
    if not len(labels) == len(mask) == len(offsets):
        return {'reason': 'length_mismatch'}
    previous = None
    active = None
    begins = Counter()
    bad = set()
    for i, tag in enumerate(labels):
        if type(tag) is not int or tag not in range(7):
            return {'reason': 'invalid_label', 'token_index': i}
        if not mask[i]:
            if tag or offsets[i] is not None:
                return {'reason': 'non_user_state_label_or_offset', 'token_index': i}
            active = None
            continue
        pair = offsets[i]
        if not valid_pair(pair, len(text)):
            return {'reason': 'invalid_raw_offset', 'token_index': i, 'slot': owner(tag)}
        if previous is not None and pair[0] < offsets[previous][1]:
            return {'reason': 'token_offset_ordering', 'token_index': i, 'previous_index': previous,
                    'previous_slot': owner(labels[previous]), 'slot': owner(tag),
                    'previous_offset': list(offsets[previous]), 'offset': list(pair)}
        previous = i
        if not tag:
            active = None
        elif tag % 2:
            active = owner(tag)
            begins[active] += 1
        elif active != owner(tag):
            bad.add(owner(tag))
            active = None
    if begins['track'] != 1:
        return {'reason': 'missing_track_begin' if not begins['track'] else 'multiple_track_begin'}
    if 'track' in bad:
        return {'reason': 'orphan_track_inside'}
    ids = [i for i, t in enumerate(labels) if t in (1, 2)]
    text_value = text[offsets[ids[0]][0]:offsets[ids[-1]][1]]
    if not text_value.strip():
        return {'reason': 'empty_track'}
    if audit.adapter.FORBIDDEN_TEXT.search(text_value):
        return {'reason': 'forbidden_track_text'}
    return {'reason': 'no_row_rejection'}


def safety_cases() -> list[dict[str, Any]]:
    """Twenty-four explicit task adversaries, reused by CPU tests and evidence."""
    cases = []
    def add(name, text, labels, offsets, expected, mask=None):
        cases.append({'name': name, 'text': text, 'labels': labels, 'offsets': offsets,
                      'mask': mask if mask is not None else [True] * len(labels), 'expected': expected})
    def play(a, b, artist=None, album=None):
        return {'intent': 'play', 'track': {'start': a, 'end': b}, 'artist': artist, 'album': album}
    for name, text, a, b in [('leading_ascii', ' abc', 1, 4), ('leading_tab', '\tabc', 1, 4),
            ('leading_em_space', '\u2003abc', 1, 4), ('trailing_whitespace', 'abc\t', 0, 3),
            ('both_whitespace', '\tabc\u2003', 1, 4), ('parentheses_retained', '(abc)', 0, 5),
            ('hyphen_retained', '-abc-', 0, 5), ('apostrophe_retained', "'abc'", 0, 5),
            ('cjk_punctuation_retained', '（歌）', 0, 3)]:
        add(name, text, [1], [(0, len(text))], play(a, b))
    add('empty_tightened', ' \t', [1], [(0, 2)], NULL)
    add('orphan_track_inside', 'abc', [2], [(0, 3)], NULL)
    add('duplicate_track_begin', 'ab', [1, 1], [(0, 1), (1, 2)], NULL)
    add('discontinuous_track', 'abc', [1, 0, 2], [(0, 1), (1, 2), (2, 3)], NULL)
    add('two_track_spans', 'abc', [1, 0, 1], [(0, 1), (1, 2), (2, 3)], NULL)
    add('invalid_raw_offset', 'abc', [1], [(-1, 3)], NULL)
    add('track_crosses_non_user', 'ab', [1, 0, 2], [(0, 1), None, (1, 2)], NULL, [True, False, True])
    add('malformed_artist_isolated', 'abc def', [1, 4], [(0, 3), (4, 7)], play(0, 3))
    add('malformed_album_isolated', 'abc def', [1, 6], [(0, 3), (4, 7)], play(0, 3))
    add('malformed_track_valid_optional', 'abc def ghi', [2, 3, 5], [(0, 3), (4, 7), (8, 11)], NULL)
    add('overlap_track_optional', 'abcdef', [1, 3], [(0, 4), (3, 6)], NULL)
    add('overlap_optional_only', 'abc defghi', [1, 3, 5], [(0, 3), (4, 8), (7, 10)], play(0, 3))
    add('no_expansion', 'xx abc yy', [1], [(2, 7)], play(3, 6))
    add('non_whitespace_never_deleted', ' -abc! ', [1], [(0, 7)], play(1, 6))
    add('literal_substring', '\u2003原曲-版本\t', [1], [(0, 7)], play(1, 6))
    return cases


def check_safety() -> dict[str, Any]:
    names = []
    for c in safety_cases():
        result = isolated(c['labels'], c['mask'], c['offsets'], c['text'], trim=True)
        audit.require(result == c['expected'], 'safety_failed:' + c['name'])
        for slot in SLOTS:
            span = result[slot]
            if span is not None:
                ids = [i for i, tag in enumerate(c['labels']) if owner(tag) == slot]
                a, b = c['offsets'][ids[0]][0], c['offsets'][ids[-1]][1]
                audit.require(a <= span['start'] < span['end'] <= b, 'safety_expansion')
                removed = c['text'][a:span['start']] + c['text'][span['end']:b]
                audit.require(all(char.isspace() for char in removed), 'safety_nonwhite_removed')
        names.append(c['name'])
    return {'passed': len(names), 'total': 24, 'cases': names}


def passed(rates: dict[str, Any]) -> bool:
    return all(rates[s]['exact'] >= GATES[s] for s in SLOTS)


def run() -> dict[str, Any]:
    audit.require(Path(sys.executable).resolve() == audit.PYTHON.resolve() and sys.flags.utf8_mode == 1, 'qualified_utf8_python')
    audit.require(os.environ.get('HF_HUB_OFFLINE') == os.environ.get('TRANSFORMERS_OFFLINE') == '1', 'offline_required')
    audit.require(all(os.environ.get(k, 'false').casefold() == 'false' for k in audit.FLAGS), 'authority_changed')
    opened, denied = set(), []
    sys.addaudithook(audit.read_guard(opened, denied))
    identity = audit.tokenizer_identity()
    prior = json.loads((audit.ROOT / 'docs/local_ai/stage_b/evidence/LAYA_SPAN_REPRESENTABILITY_AUDIT_2026-09-26.json').read_bytes())
    audit.require(prior.pop('canonical_result_sha256') == PR81_HASH == audit.canonical_hash(prior), 'pr81_identity')
    tokenizer = audit.load_tokenizer()
    config = json.loads((audit.ARTIFACT / 'rl_agent_config.json').read_bytes())
    result = {'schema': 'laya-span-seam-design-v1', 'repo_base': BASE, 'pr81_canonical_sha': PR81_HASH,
              'tokenizer_identity': identity, 'inputs': {}, 'splits': {}, 'integer_thresholds': GATES,
              'authority_flags': audit.FLAGS, 'safety_matrix': check_safety()}
    cache = {}
    for split in audit.SPLITS:
        raw = audit.split_path(split).read_bytes()
        rows = audit.parse_split(split, raw)
        result['inputs'][split] = prior['inputs'][split]
        counts = {v: Counter() for v in ('S0', 'S1', 'S2', 'S3')}
        distribution = {s: {'start_delta': Counter(), 'end_delta': Counter(), 'prefix_whitespace': Counter(),
            'suffix_whitespace': Counter(), 'languages': {}, 'templates': {}} for s in SLOTS}
        causes = []
        cache[split] = []
        denominators = Counter()
        for row in rows:
            if row.ai_scope != 'supported' or row.expected.intent != 'spotify_play_track':
                continue
            item = audit.render(row, tokenizer, config)
            labels = [tag if inside else 0 for tag, inside in zip(item['bio_labels'], item['user_state_mask'])]
            mask, offsets, text = item['user_state_mask'], item['token_offsets'], row.utterance
            s0 = audit.strict_decode(0, 1.0, labels, mask, offsets, text)
            outputs = {'S0': s0, 'S1': finish({s: s0[s] for s in SLOTS}, text, True),
                'S2': isolated(labels, mask, offsets, text), 'S3': isolated(labels, mask, offsets, text, trim=True)}
            residuals = {}
            for slot in SLOTS:
                gold = audit.raw_span(getattr(row.expected, slot))
                if gold is None:
                    continue
                denominators[slot] += 1
                ids = [i for i, tag in enumerate(labels) if owner(tag) == slot]
                first, last = offsets[ids[0]], offsets[ids[-1]]
                residuals[slot] = (gold['start'] - first[0], last[1] - gold['end'])
                for variant, output in outputs.items():
                    counts[variant][slot] += int(output[slot] == gold)
                start_delta, end_delta = first[0] - gold['start'], last[1] - gold['end']
                dist = distribution[slot]
                dist['start_delta'][str(start_delta)] += 1
                dist['end_delta'][str(end_delta)] += 1
                prefix, suffix = text[first[0]:gold['start']], text[gold['end']:last[1]]
                for key, value in [('prefix_whitespace', prefix), ('suffix_whitespace', suffix)]:
                    kind = 'empty' if not value else 'whitespace_only' if all(c.isspace() for c in value) else 'contains_non_whitespace'
                    dist[key][kind] += 1
                for key, label in [('languages', row.language_tag), ('templates', row.template_family)]:
                    slice_counts = dist[key].setdefault(label, {'rows': 0, 'start_delta': Counter(), 'end_delta': Counter()})
                    slice_counts['rows'] += 1
                    slice_counts['start_delta'][str(start_delta)] += 1
                    slice_counts['end_delta'][str(end_delta)] += 1
                interval = audit.any_interval(gold, mask, offsets, len(text))
                category = audit.classify(s0[slot], gold, interval)
                if split == 'validation' and (category == 'B' or s0[slot] is None):
                    trace = current_rejection(labels, mask, offsets, text)
                    audit.require(trace['reason'] != 'no_row_rejection', 'unclassified_missing_slot')
                    causes.append({'case_id': row.case_id, 'affected_slot': slot, 'category': category, **trace})
            cache[split].append((labels, mask, offsets, text, residuals, {s: audit.raw_span(getattr(row.expected, s)) for s in SLOTS}))
        audit.require(dict(denominators) == DENOMS[split], 'slot_denominators')
        rates = {v: {s: {'exact': counts[v][s], 'denominator': DENOMS[split][s],
                         'rate': counts[v][s] / DENOMS[split][s]} for s in SLOTS} for v in counts}
        for slot in SLOTS:
            audit.require(counts['S0'][slot] == prior['splits'][split]['slots'][slot]['current_label_roundtrip_exact'], 's0_not_reproduced')
        result['splits'][split] = {'rates': rates, 'boundary_distribution': distribution,
            'root_cause_records': causes, 'root_cause_unique_rows': len({c['case_id'] for c in causes}),
            'root_cause_affected_slots': dict(Counter(c['affected_slot'] for c in causes)),
            'root_cause_counts': dict(Counter(c['reason'] + ':' + c.get('previous_slot', '') + '->' + c.get('slot', '') for c in causes))}
        audit.require(audit.split_path(split).read_bytes() == raw, 'split_mutated')
    if passed(result['splits']['validation']['rates']['S3']):
        result['status'] = 'LAYA_SPAN_SEAM_DESIGN_S3_FEASIBLE'
        result['preferred_design'] = 'S3'
        result['rationale'] = 'All integer gates and 24 safety adversaries passed; smallest deterministic seam.'
        result['s4_evaluated'] = False
    else:
        for split, rows in cache.items():
            exact = Counter()
            for labels, mask, offsets, text, residuals, gold in rows:
                output = isolated(labels, mask, offsets, text, residuals=residuals)
                for slot in SLOTS:
                    exact[slot] += int(gold[slot] is not None and output[slot] == gold[slot])
            result['splits'][split]['rates']['S4'] = {s: {'exact': exact[s], 'denominator': DENOMS[split][s], 'rate': exact[s] / DENOMS[split][s]} for s in SLOTS}
        feasible = passed(result['splits']['validation']['rates']['S4'])
        result['status'] = 'LAYA_SPAN_SEAM_RESIDUAL_DESIGN_REQUIRED' if feasible else 'STOP_LAYA_SPAN_SEAM_DESIGN_BELOW_GATE'
        result['preferred_design'] = 'S4' if feasible else None
        result['rationale'] = 'S3 failed an integer gate; bounded gold residuals ' + ('passed.' if feasible else 'cannot cure structural rejection.')
        result['s4_evaluated'] = True
    audit.require(audit.tokenizer_identity() == identity, 'tokenizer_mutated')
    result['process_boundary'] = {'opened_corpus_splits': sorted(opened), 'protected_open_attempts': len(denied),
        'held_out_rows_opened': False, 'stage_a_rows_opened': False, 'model_weights_opened': False,
        'checkpoint_opened': False, 'model_compute_occurred': False, 'decoder_runtime_modified': False,
        'torch_imported_incidentally': 'torch' in sys.modules, 'utf8_mode': sys.flags.utf8_mode, 'offline': True}
    result['canonical_result_sha256'] = audit.canonical_hash(result)
    return result


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=True, sort_keys=True, indent=2))
