"""Tokenizer-only verification of real S3 decoder outputs against reviewed design."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import local_ai_stage_b_laya_span_decoder as implementation
import local_ai_stage_b_laya_span_seam_design as design

audit = design.audit
BASE = 'db987d26e7561391876de3e27afa113460efdde5'
DESIGN_HASH = '99bb654c9be4499054d930103416551e7583ed5c6fbf979de7ad4820274acf04'
HISTORICAL = {
    'local_ai_stage_b_laya_adapter.py': 'cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e',
    'local_ai_stage_b_laya_small_adaptation.py': '85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e',
    'local_ai_stage_b_laya_span_representability_audit.py': '6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087',
    'local_ai_stage_b_laya_span_seam_design.py': '7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72'}
EXPECTED = {'train': {'track': 886, 'artist': 612, 'album': 549},
            'validation': {'track': 297, 'artist': 126, 'album': 203}}
PASS = 'LAYA_SPAN_SEAM_S3_IMPLEMENTATION_VERIFIED'
MUTATION = 'STOP_LAYA_S3_HISTORICAL_SOURCE_MUTATED'
ORACLE = 'STOP_LAYA_S3_IMPLEMENTATION_ORACLE_MISMATCH'
DRIFT = 'STOP_LAYA_S3_IMPLEMENTATION_DESIGN_DRIFT'
BLOCKER = 'LAYA_S3_IMPLEMENTATION_NEW_BLOCKER'


def source_hashes() -> dict[str, str]:
    observed = {name: hashlib.sha256((audit.ROOT / 'scripts' / name).read_bytes()).hexdigest() for name in HISTORICAL}
    audit.require(observed == HISTORICAL, MUTATION)
    return observed


def implementation_cases() -> list[dict[str, Any]]:
    cases = []
    play = {'intent': 'play', 'track': {'start': 0, 'end': 3}, 'artist': None, 'album': None}
    def add(name, expected=None, **changes):
        case = {'name': name, 'typed_index': 0, 'validity_probability': 1.0,
                'labels': [1], 'mask': [True], 'offsets': [(0, 3)], 'text': 'abc',
                'expected': dict(implementation.NULL) if expected is None else expected}
        case.update(changes)
        cases.append(case)
    add('typed_unknown', typed_index=1)
    add('validity_below_half', validity_probability=.49)
    add('validity_nan', validity_probability=float('nan'))
    add('validity_above_one', validity_probability=1.01)
    add('length_mismatch', mask=[])
    add('invalid_label', labels=[7])
    add('non_user_label', mask=[False], offsets=[None])
    add('non_user_offset', labels=[0], mask=[False])
    add('invalid_o_offset', labels=[0], offsets=[(-1, 2)])
    moved = {**play, 'track': {'start': 3, 'end': 6}}
    add('valid_o_overlap', moved, labels=[0, 0, 1], mask=[True]*3, offsets=[(0, 1), (0, 2), (3, 6)], text='xx abc')
    add('decreasing_o_start', labels=[0, 0, 1], mask=[True]*3, offsets=[(1, 2), (0, 1), (3, 6)], text='xx abc')
    add('decreasing_o_end', labels=[0, 0, 1], mask=[True]*3, offsets=[(0, 2), (0, 1), (3, 6)], text='xx abc')
    add('track_o_overlap', labels=[1, 0], mask=[True]*2, offsets=[(0, 3), (2, 4)], text='abcd')
    for slot in ('artist', 'album'):
        tag = 3 if slot == 'artist' else 5
        add('track_' + slot + '_conflict', labels=[1, tag], mask=[True]*2, offsets=[(0, 3), (2, 4)], text='abcd')
    add('optional_conflict', play, labels=[1, 3, 5], mask=[True]*3, offsets=[(0, 3), (4, 8), (7, 10)], text='abc defghi')
    add('malformed_optional', play, labels=[1, 4], mask=[True]*2, offsets=[(0, 3), (4, 7)], text='abc def')
    add('malformed_track_clears_all', labels=[2, 3], mask=[True]*2, offsets=[(0, 3), (4, 7)], text='abc def')
    for name, text in [('forbidden_url', 'https://example.test'), ('forbidden_spotify', 'spotify:track:123'),
                       ('forbidden_path', r'C:\bad'), ('forbidden_command', 'powershell')]:
        add(name, text=text, offsets=[(0, len(text))])
    for name, text, offsets, start, end in [
            ('punctuation_not_trimmed', '(abc)', [(0, 5)], 0, 5),
            ('no_expansion', 'xx abc yy', [(2, 7)], 3, 6),
            ('literal_substring', '\u2003原曲-版本\t', [(0, 7)], 1, 6)]:
        add(name, {**play, 'track': {'start': start, 'end': end}}, text=text, offsets=offsets)
    add('empty_after_tightening', text=' \t', offsets=[(0, 2)])
    return cases


def safety_inventory() -> dict[str, Any]:
    reviewed = []
    for c in design.safety_cases():
        actual = implementation.decode(0, 1.0, c['labels'], c['mask'], c['offsets'], c['text'])
        audit.require(actual == c['expected'], BLOCKER + ':reviewed_safety:' + c['name'])
        reviewed.append(c['name'])
    added = []
    for c in implementation_cases():
        actual = implementation.decode(**{k: v for k, v in c.items() if k not in ('name', 'expected')})
        audit.require(actual == c['expected'], BLOCKER + ':implementation_safety:' + c['name'])
        added.append(c['name'])
    source_hashes()
    added += ['historical_decoder_hash_unchanged', 'design_helper_hash_unchanged']
    audit.require(len(reviewed) == 24 and len(added) == 28, BLOCKER + ':inventory')
    audit.require(implementation.adapter.FORBIDDEN_TEXT is audit.adapter.FORBIDDEN_TEXT, BLOCKER + ':forbidden_policy')
    return {'reviewed': {'passed': 24, 'total': 24, 'cases': reviewed},
            'implementation': {'passed': 28, 'total': 28, 'cases': added},
            'forbidden_text': {'passed': 4, 'total': 4, 'exact_adapter_policy_reused': True}}


def check_counts(split: str, counts: dict[str, int], denominators: dict[str, int]) -> None:
    audit.require(counts == EXPECTED[split] and denominators == design.DENOMS[split], ORACLE)


def verify_rows(split: str, rows: list[Any], tokenizer: Any, config: dict[str, Any]) -> dict[str, Any]:
    actual_counts, design_counts, denominators = Counter(), Counter(), Counter()
    total = 0
    failures = {s: [] for s in audit.SLOTS}
    for row in rows:
        if row.ai_scope != 'supported' or row.expected.intent != 'spotify_play_track':
            continue
        item = audit.render(row, tokenizer, config)
        labels = [tag if inside else 0 for tag, inside in zip(item['bio_labels'], item['user_state_mask'])]
        args = (labels, item['user_state_mask'], item['token_offsets'], row.utterance)
        reference = design.isolated(*args, trim=True)
        actual = implementation.decode(0, 1.0, *args)
        audit.require(actual == reference, DRIFT)
        total += 1
        for slot in audit.SLOTS:
            gold = audit.raw_span(getattr(row.expected, slot))
            if gold is None:
                continue
            denominators[slot] += 1
            actual_counts[slot] += int(actual[slot] == gold)
            design_counts[slot] += int(reference[slot] == gold)
            if actual[slot] != gold:
                failures[slot].append({'case_id': row.case_id, 'gold': gold, 'actual': actual[slot]})
    check_counts(split, dict(actual_counts), dict(denominators))
    check_counts(split, dict(design_counts), dict(denominators))
    audit.require(total == design.DENOMS[split]['track'], DRIFT)
    return {'implementation_exact': dict(actual_counts), 'design_exact': dict(design_counts),
            'denominators': dict(denominators), 'parity': {'total': total, 'equal': total, 'mismatches': 0},
            'retained_non_exact': failures}


def run() -> dict[str, Any]:
    audit.require(Path(sys.executable).resolve() == audit.PYTHON.resolve() and sys.flags.utf8_mode == 1, BLOCKER + ':python_utf8')
    audit.require(os.environ.get('HF_HUB_OFFLINE') == os.environ.get('TRANSFORMERS_OFFLINE') == '1', BLOCKER + ':offline')
    audit.require(all(os.environ.get(k, 'false').casefold() == 'false' for k in audit.FLAGS), BLOCKER + ':authority')
    opened, denied = set(), []
    sys.addaudithook(audit.read_guard(opened, denied))
    historical_before = source_hashes()
    identity = audit.tokenizer_identity()
    reviewed = json.loads((audit.ROOT / 'docs/local_ai/stage_b/evidence/LAYA_SPAN_SEAM_DESIGN_RESULT_2026-09-26.json').read_bytes())
    audit.require(reviewed.pop('canonical_result_sha256') == DESIGN_HASH == audit.canonical_hash(reviewed), BLOCKER + ':design_identity')
    result = {'schema': 'laya-s3-implementation-v1', 'repo_base': BASE, 'reviewed_design_sha': DESIGN_HASH,
              'tokenizer_identity': identity, 'historical_before': historical_before, 'authority_flags': audit.FLAGS,
              'safety_inventory': safety_inventory(), 'inputs': {}, 'splits': {}}
    tokenizer = audit.load_tokenizer()
    config = json.loads((audit.ARTIFACT / 'rl_agent_config.json').read_bytes())
    for split in audit.SPLITS:
        raw = audit.split_path(split).read_bytes()
        rows = audit.parse_split(split, raw)
        result['splits'][split] = verify_rows(split, rows, tokenizer, config)
        result['inputs'][split] = reviewed['inputs'][split]
        audit.require(audit.split_path(split).read_bytes() == raw, BLOCKER + ':split_mutated')
    result['historical_after'] = source_hashes()
    audit.require(historical_before == result['historical_after'], MUTATION)
    audit.require(audit.tokenizer_identity() == identity, BLOCKER + ':tokenizer_mutated')
    result['source_hashes'] = {name: hashlib.sha256((audit.ROOT / 'scripts' / name).read_bytes()).hexdigest()
        for name in ('local_ai_stage_b_laya_span_decoder.py', Path(__file__).name)}
    result['process_boundary'] = {'opened_corpus_splits': sorted(opened), 'protected_open_attempts': len(denied),
        'held_out_rows_opened': False, 'stage_a_rows_opened': False, 'model_weights_opened': False,
        'checkpoint_opened': False, 'gpu_access': False, 'model_compute': False, 'app_modified': False,
        'torch_imported_incidentally': 'torch' in sys.modules, 'utf8_mode': sys.flags.utf8_mode, 'offline': True}
    result['train_album_limitation'] = {'exact': 549, 'denominator': 582, 'rate': 549 / 582, 'nonwhite_trim_forbidden': True}
    result['status'] = PASS
    result['canonical_result_sha256'] = audit.canonical_hash(result)
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(run(), ensure_ascii=True, sort_keys=True, indent=2))
    except (ValueError, PermissionError) as error:
        reason = str(error)
        label = reason if reason in (MUTATION, ORACLE, DRIFT) else BLOCKER
        print(json.dumps({'status': label, 'blocker': reason}))
        raise SystemExit(1)
