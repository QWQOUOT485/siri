"""One validation pass for PR88-bound Laya BIO and typed-decision diagnosis."""
from __future__ import annotations

import argparse
import atexit
from collections import Counter
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from typing import Any

import local_ai_stage_b_laya_base_load_root_cause as load_guard
import local_ai_stage_b_laya_s3_pr79_validation_diagnostic as prior
import local_ai_stage_b_laya_s3_pr79_validation_diagnostic_retry as reviewed

pinned, historical, smoke, ROOT = prior.pinned, prior.historical, prior.smoke, prior.ROOT
BASE = 'b6af8e4c4599647b16273c5ece6f21360b9d5e5c'
AUTHORIZATION = 'laya-span-typed-diagnosis-v1'
PASS, BLOCKER = 'LAYA_SPAN_TYPED_DIAGNOSIS_COMPLETED', 'LAYA_SPAN_TYPED_DIAGNOSIS_NEW_BLOCKER'
REPRODUCTION = 'STOP_LAYA_SPAN_TYPED_REPRODUCTION_MISMATCH'
TAXONOMY = 'STOP_LAYA_SPAN_DIAGNOSIS_TAXONOMY_INCOMPLETE'
DATA = 'STOP_LAYA_SPAN_TYPED_DATA_BOUNDARY'
CHECKPOINT = 'STOP_LAYA_SPAN_TYPED_CHECKPOINT_IDENTITY'
RESTORE = 'STOP_LAYA_SPAN_TYPED_RESTORE_MISMATCH'
DEVICE = 'STOP_LAYA_SPAN_TYPED_DEVICE_MISMATCH'
SCRATCH = Path(r'D:\ai\ai\stage_b_laya_diagnosis\span-typed-v1')
RESULT = ROOT / 'docs/local_ai/stage_b/evidence/LAYA_SPAN_TYPED_DIAGNOSIS_2026-09-28.json'
PR88 = ROOT / 'docs/local_ai/stage_b/evidence/LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_RETRY_2026-09-27.json'
PR88_SHA = 'babb424a086de8bbf83ff5ab68a91dcea39cb5ae1e1247dc5347a1cd40f6a42b'
PREFIX = 'LAYA_SPAN_TYPED_DIAGNOSIS='
PREFLIGHT = 'LAYA_SPAN_TYPED_DIAGNOSIS_PREFLIGHT_PASSED_NO_COMPUTE'
CACHE_BINDINGS = load_guard.CACHE_BINDINGS
canonical_hash, sha, require = prior.canonical_hash, prior.sha, prior.require
LABELS = ('O', 'B-TRACK', 'I-TRACK', 'B-ARTIST', 'I-ARTIST', 'B-ALBUM', 'I-ALBUM')
SLOTS = {'track': (1, 2), 'artist': (3, 4), 'album': (5, 6)}
TAXONOMY_ORDER = ('track_labels_absent', 'track_orphan_inside_only',
    'track_multiple_begin_or_multiple_spans', 'track_begin_without_contiguous_inside',
    'track_invalid_selected_offset', 'track_conflict_with_selected_optional',
    'track_forbidden_or_empty_after_tightening', 'track_other_decoder_rejection')
EVIDENCE = {
 'LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json': prior.research.PR79_SHA,
 'LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json': prior.research.IMPLEMENTATION_SHA,
 'LAYA_S3_RESEARCH_PATH_PREFLIGHT_2026-09-27.json': '38bdead38e5dea83cf45e522279e7280fdfa0aeb08d8d6e12984cff1d7591d87',
 'LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json': 'ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd',
 'LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_2026-09-27.json': '962b0f0b720fd87cb21b7a22cadc228150733327e2dfcc318628de28194f5535'}
EVIDENCE['LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_RETRY_2026-09-27.json'] = PR88_SHA


class Audit(load_guard.Audit):
    """Only add exact read-only validation/checkpoint exceptions to the reviewed write policy."""
    def __init__(self):
        super().__init__(SCRATCH)
        self.allowed_reads = {'validation': 0, 'pr79_checkpoint': 0, 'pr88_evidence': 0}

    def deny(self, label: str, event: str, info: dict[str, Any]) -> None:
        super().deny({load_guard.DATA: DATA, load_guard.CHECKPOINT: CHECKPOINT,
            load_guard.PROTECTED: 'STOP_LAYA_SPAN_TYPED_PROTECTED_WRITE',
            load_guard.OUTSIDE: 'STOP_LAYA_SPAN_TYPED_UNEXPECTED_WRITE',
            load_guard.NETWORK: 'STOP_LAYA_SPAN_TYPED_NETWORK'}.get(label, label), event, info)

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            path, mode, flags = args[:3]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int)
                and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if not writing:
                lexical = Path(os.fsdecode(path)).absolute()
                resolved = lexical.resolve()
                for name, allowed in (('validation', prior.VALIDATION), ('pr79_checkpoint', prior.CHECKPOINT_PATH),
                                      ('pr88_evidence', PR88)):
                    if (lexical == allowed) != (resolved == allowed):
                        self.deny(DATA if name=='validation' else CHECKPOINT if name=='pr79_checkpoint' else REPRODUCTION,
                            event,{'path_category':'redirected_exact_read'})
                    if lexical == resolved == allowed:
                        self.allowed_reads[name] += 1
                        return
        super().__call__(event, args)


def exception_record(exc: BaseException, stage: str) -> dict[str, Any]:
    record = load_guard.exception_record(exc, stage)
    for name in ('filename', 'filename2'):
        value = getattr(exc, name, None)
        if value is not None:
            record[name] = {'path_category': load_guard.category(value, SCRATCH)['path_category'],
                'basename': Path(os.fsdecode(value)).name}
    return record


def failure_record(exc: BaseException) -> dict[str, Any]:
    record = prior.failure_record(exc)
    record['blocker'] = load_guard.sanitized_message(record['blocker'])
    direct = str(exc).split(':',1)[0]
    own_labels = (REPRODUCTION,TAXONOMY,DATA,CHECKPOINT,RESTORE,DEVICE,
        'STOP_LAYA_SPAN_TYPED_PROTECTED_WRITE','STOP_LAYA_SPAN_TYPED_UNEXPECTED_WRITE',
        'STOP_LAYA_SPAN_TYPED_NETWORK')
    if direct in own_labels:
        record['status'] = direct
    else:
        record['status'] = {prior.BLOCKER: BLOCKER, prior.DATA: DATA, prior.CHECKPOINT: CHECKPOINT,
        prior.RESTORE: RESTORE, prior.DEVICE: DEVICE, prior.REPRODUCTION: REPRODUCTION}.get(record['status'], record['status'])
    return record


def identities() -> tuple[dict[str, Any], list[Any], dict[str, Any], dict[str, Any]]:
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve() and sys.version_info[:3] == (3, 14, 7), BLOCKER, 'python')
    require(sys.flags.utf8_mode == 1 and sys.dont_write_bytecode, BLOCKER, 'process_flags')
    prior.authority_check()
    require(os.environ.get('HF_HUB_OFFLINE') == os.environ.get('TRANSFORMERS_OFFLINE') == '1'
        and not os.environ.get('PYTHONPATH'), BLOCKER, 'offline')
    require(prior.git('rev-parse', 'origin/main') == prior.git('merge-base', 'HEAD', BASE) == BASE, 'STOP_REVIEWED_STATE_CHANGED')
    versions = {name: importlib.metadata.version(name) for name in pinned.EXPECTED_PACKAGES}
    require(versions == pinned.EXPECTED_PACKAGES and importlib.metadata.version('torch') == '2.13.0+rocm10.0.0', BLOCKER, 'packages')
    inventory = pinned.package_inventory()
    require(inventory == '3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337', BLOCKER, 'venv')
    sources = {}
    for path in sorted((ROOT / 'scripts').glob('local_ai_stage_b_laya*.py')):
        if path.resolve() == Path(__file__).resolve():
            continue
        relative = path.relative_to(ROOT).as_posix()
        require(prior.git('hash-object', str(path)) == prior.git('rev-parse', BASE + ':' + relative), prior.SOURCE)
        sources[path.name] = sha(path)
    prior.source_identity()
    require(sources['local_ai_stage_b_laya_s3_pr79_validation_diagnostic.py'] == '4b259bd9629628aeb3d25ad231521a745cfec81ac0ea6ce6786386259ef94b4f'
        and sources['local_ai_stage_b_laya_base_load_root_cause.py'] == '5e82645ec396509155fcb85d9d24989729be84ce81b08e550e32e5a3098f163e'
        and sources['local_ai_stage_b_laya_s3_pr79_validation_diagnostic_retry.py'] == '48c081e68255e6bb8aa86886c03b4673567f6f9666497ba9fec10e8df2c1a567'
        and sources['local_ai_stage_b_laya_span_decoder.py'] == 'f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845', prior.SOURCE)
    evidence = {}
    for name, digest in EVIDENCE.items():
        prior.research.canonical_evidence(name, digest)
        evidence[name] = {'canonical_sha256': digest, 'byte_sha256': sha(ROOT / 'docs/local_ai/stage_b/evidence' / name)}
    reports = {path.name: sha(path) for path in (ROOT / 'docs/local_ai/stage_b/evidence').glob('LOCAL_AI_STAGE_B_LAYA*.md')
        if 'DIAGNOSTIC_RETRY' not in path.name}
    accepted = prior.accepted_evidence()
    pr88 = json.loads(PR88.read_bytes())
    require(pr88.pop('canonical_result_sha256') == canonical_hash(pr88) == PR88_SHA
        and pr88['status'] == reviewed.PASS, REPRODUCTION, 'pr88_identity')
    checkpoint = prior.checkpoint_identity()
    require(prior.VALIDATION.resolve() == prior.VALIDATION, prior.DATA, 'validation_redirected')
    try:
        rows = historical.parse_validation(prior.VALIDATION.read_bytes())
        composition = historical.validate_validation(rows)
    except Exception as exc:
        raise ValueError(prior.DATA + ':validation_identity_or_schema') from exc
    model = prior.model_identity()
    tokenizer = prior.audit.tokenizer_identity()
    config = json.loads((pinned.MODEL / 'tokenizer/tokenizer_config.json').read_bytes())
    require(config.get('tokenizer_class') not in (None, 'TokenizersBackend')
        and not isinstance(config.get('extra_special_tokens'), list), BLOCKER, 'tokenizer_fix_not_noop')
    return {'historical_sources': sources, 'accepted_evidence': evidence, 'historical_reports': reports,
        'source_revision': pinned.source_identity(), 'source_clean': True, 'model': model, 'tokenizer': tokenizer,
        'venv_inventory': inventory, 'package_versions': versions, 'checkpoint': checkpoint,
        'validation_sha256': sha(prior.VALIDATION), 'validation_composition': composition}, rows, accepted, pr88


def scratch_safe(absent: bool = False) -> None:
    require(SCRATCH.is_absolute() and SCRATCH.name == 'span-typed-v1', BLOCKER, 'scratch_identity')
    for root in load_guard.PROTECTED_ROOTS.values():
        require(not load_guard.under(SCRATCH, root) and not load_guard.under(root, SCRATCH), BLOCKER, 'scratch_overlap')
    for path in (SCRATCH, *SCRATCH.parents):
        if path.exists():
            require(not path.is_symlink() and not path.is_junction()
                and not path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, BLOCKER, 'scratch_redirected')
    if absent:
        require(not SCRATCH.exists(), BLOCKER, 'scratch_preexists')


def preflight() -> dict[str, Any]:
    guard = Audit()
    sys.addaudithook(guard)
    identity, _, _, _ = identities()
    guard.check()
    scratch_safe(absent=True)
    require(not RESULT.exists(), BLOCKER, 'durable_result_preexists')
    return {'status': PREFLIGHT, 'repo_base': BASE, 'runner_sha256': sha(Path(__file__)), 'identities': identity,
        'authority_flags': dict(prior.audit.FLAGS), 'audit': guard.summary(), 'allowed_reads': guard.allowed_reads,
        'model_loads': 0, 'checkpoint_deserializations': 0, 'validation_passes': 0}


def user_record(row: Any, item: dict[str, Any], typed: int, probability: float,
                validity: float, labels: list[int]) -> dict[str, Any]:
    mask = item['user_state_mask']
    require(len(labels) >= len(mask), DATA, 'predicted_labels_short')
    indices = [i for i, inside in enumerate(mask) if inside]
    gold = [item['bio_labels'][i] for i in indices]
    predicted = [labels[i] for i in indices]
    offsets = [item['token_offsets'][i] for i in indices]
    require(all(type(x) is int and x in range(7) for x in gold + predicted)
        and all(prior.research.s3_decoder.valid_pair(x, len(row.utterance)) for x in offsets), DATA, 'user_bio_geometry')
    return {'case_id': row.case_id, 'language_tag': row.language_tag,
        'gold_intent': row.expected.intent, 'typed_index': typed,
        'typed_play_probability': probability, 'validity_probability': validity,
        'user_token_count': len(indices), 'masked_predicted_bio_label_ids': predicted,
        'gold_bio_label_ids': gold, 'token_offsets': offsets}


def confusion(records: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = [[0] * 7 for _ in range(7)]
    for record in records:
        for gold, predicted in zip(record['gold_bio_label_ids'], record['masked_predicted_bio_label_ids']):
            matrix[gold][predicted] += 1
    classes = {}
    for i in range(1, 7):
        support = sum(matrix[i]); predicted = sum(row[i] for row in matrix); tp = matrix[i][i]
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        classes[LABELS[i]] = {'support': support, 'predicted': predicted, 'true_positive': tp,
            'false_positive': predicted-tp, 'false_negative': support-tp,
            'precision': precision, 'recall': recall,
            'f1': 2*tp/(support+predicted) if support+predicted else 0.0}
    tp = sum(matrix[i][i] for i in range(1, 7))
    support = sum(x['support'] for x in classes.values())
    predicted = sum(x['predicted'] for x in classes.values())
    return {'matrix': matrix, 'user_token_total': sum(map(sum, matrix)), 'classes': classes,
        'micro': {'precision': tp/predicted if predicted else 0.0,
            'recall': tp/support if support else 0.0,
            'f1': 2*tp/(support+predicted) if support+predicted else 0.0},
        'macro': {k: sum(x[k] for x in classes.values())/6 for k in ('precision','recall','f1')}}


def quantile(values: list[float], fraction: float) -> float:
    require(bool(values) and 0 <= fraction <= 1, DATA, 'quantile_input')
    ordered = sorted(values); position = (len(values)-1)*fraction
    lower = math.floor(position); upper = math.ceil(position)
    return ordered[lower] + (position-lower)*(ordered[upper]-ordered[lower])


def margins(values: list[float], below: bool) -> dict[str, int]:
    bands = dict.fromkeys(('0.00-0.02','0.02-0.05','0.05-0.10','0.10-0.20','>0.20'), 0)
    for value in values:
        if (value < .5) != below:
            continue
        distance = abs(value-.5)
        key = next((key for key, cap in zip(bands, (.02,.05,.10,.20)) if distance < cap), '>0.20')
        bands[key] += 1
    return bands


def distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [r['typed_play_probability'] for r in records]
    require(all(type(v) is float and math.isfinite(v) and 0 <= v <= 1 for v in values), DATA, 'typed_probabilities')
    return {'count': len(values), 'min': min(values), 'max': max(values), 'mean': sum(values)/len(values),
        'quantiles': {f'p{int(p*100):02d}': quantile(values,p) for p in (.05,.10,.25,.50,.75,.90,.95)},
        'below_0_5': sum(v < .5 for v in values), 'at_or_above_0_5': sum(v >= .5 for v in values),
        'distance_below_0_5': margins(values, True), 'distance_at_or_above_0_5': margins(values, False)}


def track_geometry(tags: list[int]) -> dict[str, Any]:
    ids = [i for i, tag in enumerate(tags) if tag in (1,2)]
    begins = [i for i in ids if tags[i] == 1]
    runs = 0
    for i in ids:
        if i-1 not in ids: runs += 1
    return {'begin_count': len(begins), 'any_inside': any(tags[i] == 2 for i in ids),
        'orphan_inside': any(tags[i] == 2 and (i == 0 or tags[i-1] not in (1,2)) for i in ids),
        'run_count': runs, 'selected_indices': ids}


def taxonomy(tags: list[int], offsets: list[Any], text: str) -> dict[str, Any]:
    """Frozen precedence; every residual requires an explicit decoder geometry trace."""
    decoder = prior.research.s3_decoder
    require(len(tags) == len(offsets) and all(type(t) is int and t in range(7) for t in tags), TAXONOMY, 'input')
    info = track_geometry(tags); ids = info['selected_indices']
    require(decoder.decode(0, .9, tags, [True]*len(tags), offsets, text)['intent'] == 'unknown', TAXONOMY, 'not_rejected')
    category = trace = None
    if not ids: category, trace = TAXONOMY_ORDER[0], {'code':'no_track_tags'}
    elif info['begin_count'] == 0: category, trace = TAXONOMY_ORDER[1], {'code':'inside_without_begin','indices':ids}
    elif info['begin_count'] > 1 or info['run_count'] > 1:
        category, trace = TAXONOMY_ORDER[2], {'code':'multiple_begin_or_separated_runs','indices':ids,'run_count':info['run_count']}
    elif tags[ids[0]] != 1 or any(tags[i] != 2 for i in ids[1:]):
        category, trace = TAXONOMY_ORDER[3], {'code':'begin_not_first_or_inside_broken','indices':ids}
    elif any(not decoder.valid_pair(offsets[i],len(text)) for i in ids):
        category, trace = TAXONOMY_ORDER[4], {'code':'selected_offset_invalid','indices':[i for i in ids if not decoder.valid_pair(offsets[i],len(text))]}
    else:
        conflicts = [(i,j) for i in ids for j,t in enumerate(tags) if t in (3,4,5,6)
            and decoder.valid_pair(offsets[j],len(text)) and offsets[j][0] < offsets[i][1]
            and offsets[i][0] < offsets[j][1]]
        if conflicts: category, trace = TAXONOMY_ORDER[5], {'code':'track_optional_overlap','index_pairs':conflicts}
        else:
            selected = {'start':offsets[ids[0]][0], 'end':offsets[ids[-1]][1]}
            tight = decoder.tighten(text,selected)
            if tight is None or decoder.adapter.FORBIDDEN_TEXT.search(text[tight['start']:tight['end']]):
                category, trace = TAXONOMY_ORDER[6], {'code':'empty_or_forbidden_after_tightening','indices':ids}
            else:
                reversed_o = [(i,j) for i,t in enumerate(tags) if t == 0 for j in range(i+1,len(tags))
                    if tags[j] == 0 and decoder.valid_pair(offsets[i],len(text))
                    and decoder.valid_pair(offsets[j],len(text))
                    and (offsets[j][0] < offsets[i][0] or offsets[j][1] < offsets[i][1])]
                selected_o = [(i,j) for i in ids for j,t in enumerate(tags) if t == 0
                    and decoder.valid_pair(offsets[j],len(text)) and offsets[j][0] < offsets[i][1]
                    and offsets[i][0] < offsets[j][1]]
                selected_self = [(i,j) for pos,i in enumerate(ids) for j in ids[pos+1:]
                    if offsets[j][0] < offsets[i][1]]
                if reversed_o: trace = {'code':'unselected_o_order_reversal','index_pairs':reversed_o}
                elif selected_o: trace = {'code':'track_o_offset_overlap','index_pairs':selected_o}
                elif selected_self: trace = {'code':'selected_track_offset_overlap','index_pairs':selected_self}
                category = TAXONOMY_ORDER[7]
    require(category is not None and trace is not None and trace.get('code'), TAXONOMY, 'missing_trace')
    if category == TAXONOMY_ORDER[7]:
        require(trace.get('index_pairs'), TAXONOMY, 'other_without_machine_checkable_cause')
    return {'category':category,'trace':trace}


def optional_structural(tags: list[int], offsets: list[Any], text: str, slot: str) -> bool:
    decoder=prior.research.s3_decoder
    begin,inside=SLOTS[slot]
    ids=[i for i,x in enumerate(tags) if x in (begin,inside)]
    if (not ids or tags[ids[0]] != begin or any(tags[i] != inside for i in ids[1:])
            or ids != list(range(ids[0],ids[-1]+1))):
        return False
    if any(not decoder.valid_pair(x,len(text)) for x in offsets):
        return False
    for i,left in enumerate(offsets):
        for j in range(i+1,len(offsets)):
            right=offsets[j]
            if tags[i]==tags[j]==0 and (right[0]<left[0] or right[1]<left[1]):return False
            if right[0]<left[1] and (i in ids or j in ids):return False
    raw={'start':offsets[ids[0]][0],'end':offsets[ids[-1]][1]}
    tight=decoder.tighten(text,raw)
    return tight is not None and not decoder.adapter.FORBIDDEN_TEXT.search(text[tight['start']:tight['end']])


def span_coverage(records: list[dict[str, Any]], slot: str, rows_by_id: dict[str, Any]) -> dict[str, int]:
    begin, inside = SLOTS[slot]
    counts = dict.fromkeys(('gold_rows','gold_begin_correct','any_correct_token','all_gold_tokens_o',
        'all_gold_tokens_wrong_slot','partial_correct_slot','exact_gold_bio_sequence',
        'predicted_as_track','predicted_as_wrong_optional','correct_b_broken_i','structurally_valid_if_track_ignored'),0)
    for r in records:
        gold, pred, offsets = r['gold_bio_label_ids'], r['masked_predicted_bio_label_ids'], r['token_offsets']
        ids = [i for i,x in enumerate(gold) if x in (begin,inside)]
        if not ids: continue
        counts['gold_rows'] += 1
        values = [pred[i] for i in ids]
        matched = sum(pred[i] == gold[i] for i in ids)
        counts['gold_begin_correct'] += int(pred[ids[0]] == begin)
        counts['any_correct_token'] += int(matched > 0)
        counts['all_gold_tokens_o'] += int(all(x == 0 for x in values))
        counts['all_gold_tokens_wrong_slot'] += int(all(x not in (0,begin,inside) for x in values))
        counts['partial_correct_slot'] += int(0 < matched < len(ids))
        counts['exact_gold_bio_sequence'] += int(matched == len(ids))
        counts['predicted_as_track'] += int(any(x in (1,2) for x in values))
        counts['predicted_as_wrong_optional'] += int(any(x in (3,4,5,6) and x not in (begin,inside) for x in values))
        counts['correct_b_broken_i'] += int(pred[ids[0]] == begin and any(pred[i] != inside for i in ids[1:]))
        counts['structurally_valid_if_track_ignored'] += int(optional_structural(
            pred,offsets,rows_by_id[r['case_id']].utterance,slot))
    return counts


def sanitization_check(value: Any, forbidden_texts: list[str] = ()) -> None:
    import re
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                require(not any(word in key.lower() for word in ('utterance','token_text','substring','raw_path')),
                    DATA,'sensitive_key')
                walk(child)
        elif isinstance(node,list):
            for child in node: walk(child)
        elif isinstance(node,str):
            require(not re.search(r'[A-Za-z]:[\\/]|\\\\[^\\]|[A-Za-z]:/',node), DATA,'absolute_path')
            require(not any(text and text in node for text in forbidden_texts), DATA, 'utterance_text')
    walk(value)


def validation_pass(result: dict[str, Any], rows: list[Any], items: list[Any], infer: Any, guard: Audit):
    """Fixed coverage once; infer returns one set of raw shared decisions per batch."""
    counts = result['execution_counts']
    require(counts['validation_passes'] == 0 and len(rows) == len(items) == 540
        and len({r.case_id for r in rows}) == 540 and all(r.ai_scope == 'supported' for r in rows), prior.DATA, 'validation_coverage')
    counts['validation_passes'] += 1
    old, new, decisions, batches, token_records = [], [], [], [], []
    for start in range(0, 540, 16):
        guard.check()
        batch_rows, batch_items = rows[start:start + 16], items[start:start + 16]
        counts['validation_forward_batches'] += 1
        typed, probabilities, validities, labels = infer(batch_items)
        guard.check()
        require(len(typed) == len(probabilities) == len(validities) == len(labels) == len(batch_rows), DATA, 'inference_batch_size')
        a, b, c = prior.dual_decode(batch_rows, batch_items, typed, probabilities, validities, labels)
        old.extend(a); new.extend(b); decisions.extend(c)
        token_records.extend(user_record(*args) for args in zip(batch_rows,batch_items,typed,probabilities,validities,labels))
        for key in ('shared_model_decisions', 'historical_decoder_calls', 's3_decoder_calls'):
            counts[key] += len(batch_rows)
        batches.append([r.case_id for r in batch_rows])
    require([len(b) for b in batches] == [16] * 33 + [12], prior.DATA, 'batches')
    result['batch_case_ids'] = batches
    return old, new, decisions, token_records


def reproduce(rows: list[Any], old: list[Any], new: list[Any], decisions: list[Any], pr88: dict[str, Any]) -> dict[str, Any]:
    require(len(rows) == len(old) == len(new) == len(decisions) == 540, REPRODUCTION, 'count')
    expected = pr88['shared_decisions']
    a,b = pr88['historical']['predictions'], pr88['s3']['predictions']
    require(len(expected) == len(a) == len(b) == 540, REPRODUCTION, 'pr88_count')
    mismatches = dict(case_id=[],typed_index=[],validity_gate=[],historical=[],s3=[])
    probability_deltas = {'typed_play_probability':[], 'validity_probability':[]}
    for row,pred_old,pred_new,decision,want,x,y in zip(rows,old,new,decisions,expected,a,b):
        if not row.case_id == decision['case_id'] == want['case_id'] == x['case_id'] == y['case_id']:
            mismatches['case_id'].append(row.case_id)
        if decision['typed_index'] != want['typed_index']: mismatches['typed_index'].append(row.case_id)
        if (decision['validity_probability'] >= .5) != (want['validity_probability'] >= .5):
            mismatches['validity_gate'].append(row.case_id)
        if {'case_id':row.case_id,**pred_old} != x: mismatches['historical'].append(row.case_id)
        if {'case_id':row.case_id,**pred_new} != y: mismatches['s3'].append(row.case_id)
        for key in probability_deltas:
            probability_deltas[key].append(abs(decision[key]-want[key]))
    require(not any(mismatches.values()), REPRODUCTION, 'decision_or_prediction')
    return {'exact_decision_prediction_matches':540, 'mismatch_case_ids':mismatches,
        'probability_exact_rows':{key:sum(x == 0 for x in values) for key,values in probability_deltas.items()},
        'max_absolute_probability_delta':{key:max(values) for key,values in probability_deltas.items()},
        'argmax_and_validity_gate_unchanged':True}


def diagnose(rows: list[Any], records: list[dict[str, Any]], new: list[Any], pr88: dict[str, Any]) -> dict[str, Any]:
    require(len(rows) == len(records) == len(new) == 540, DATA, 'analysis_count')
    decoder = prior.research.s3_decoder
    lookup = {r.case_id:(r,rec,pred) for r,rec,pred in zip(rows,records,new)}
    play = [rec for rec in records if rec['gold_intent'] == 'spotify_play_track']
    unknown = [rec for rec in records if rec['gold_intent'] == 'unknown']
    require(len(play)==300 and len(unknown)==240,DATA,'analysis_class_counts')
    taxonomy_ids = pr88['analysis']['play_failure_case_ids']['s3_track_invalid_or_missing']
    typed_ids = pr88['analysis']['play_failure_case_ids']['typed_not_play']
    require(len(taxonomy_ids)==len(set(taxonomy_ids))==218 and len(typed_ids)==len(set(typed_ids))==70
        and not set(taxonomy_ids)&set(typed_ids), REPRODUCTION,'pr88_bucket_ids')
    classified = {key:[] for key in TAXONOMY_ORDER}; traces = {}
    for case in taxonomy_ids:
        row,rec,pred = lookup[case]
        require(pred['intent']=='unknown' and rec['typed_index']==0, TAXONOMY,'unexpected_bucket_state')
        value=taxonomy(rec['masked_predicted_bio_label_ids'],rec['token_offsets'],row.utterance)
        classified[value['category']].append(case);traces[case]=value['trace']
    require(set(traces)==set(taxonomy_ids) and sum(map(len,classified.values()))==218, TAXONOMY,'coverage')
    counter = dict(structurally_invalid_or_missing_track=0,structurally_valid_track=0,
        structurally_exact_track=0, structurally_full_semantic_exact=0,
        typed_only_would_emit_track=0,typed_only_track_exact=0,
        typed_only_full_semantic_exact=0,validity_blocked_structurally_valid=0)
    counter_cases={key:[] for key in counter}
    track_matrix = {'typed_play':{'valid_track':0,'invalid_or_missing_track':0,'track_exact':0,'track_non_exact':0},
                    'typed_not_play':{'valid_track':0,'invalid_or_missing_track':0,'track_exact':0,'track_non_exact':0}}
    structure={lang:{key:0 for key in ('zero_begin','one_begin','multiple_begin','any_inside','orphan_inside',
        'one_contiguous_run','multiple_runs','s3_track_emitted','s3_track_exact','s3_track_non_exact')}
        for lang in ('all','mixed','en','typed_play','typed_not_play','mixed_typed_play',
            'mixed_typed_not_play','en_typed_play','en_typed_not_play')}
    for rec in play:
        row,_,pred=lookup[rec['case_id']]
        tags=rec['masked_predicted_bio_label_ids']; offsets=rec['token_offsets']; geo=track_geometry(tags)
        structural=decoder.decode(0,1.0,tags,[True]*len(tags),offsets,row.utterance)
        valid=structural['track'] is not None
        exact=valid and structural['track']==prior.gold(row)['track']
        matrix=track_matrix['typed_play' if rec['typed_index']==0 else 'typed_not_play']
        matrix['valid_track' if valid else 'invalid_or_missing_track']+=1
        matrix['track_exact' if exact else 'track_non_exact']+=1
        if rec['case_id'] in typed_ids:
            key='structurally_valid_track' if valid else 'structurally_invalid_or_missing_track'
            counter[key]+=1;counter_cases[key].append(rec['case_id'])
            if exact: counter['structurally_exact_track']+=1;counter_cases['structurally_exact_track'].append(rec['case_id'])
            if structural=={'intent':'play',**prior.gold(row)}:
                counter['structurally_full_semantic_exact']+=1;counter_cases['structurally_full_semantic_exact'].append(rec['case_id'])
            typed_only=decoder.decode(0,rec['validity_probability'],tags,[True]*len(tags),offsets,row.utterance)
            if typed_only['track'] is not None:
                counter['typed_only_would_emit_track']+=1;counter_cases['typed_only_would_emit_track'].append(rec['case_id'])
            if typed_only['track']==prior.gold(row)['track']:
                counter['typed_only_track_exact']+=1;counter_cases['typed_only_track_exact'].append(rec['case_id'])
            if typed_only=={'intent':'play',**prior.gold(row)}:
                counter['typed_only_full_semantic_exact']+=1;counter_cases['typed_only_full_semantic_exact'].append(rec['case_id'])
            if valid and typed_only['track'] is None and rec['validity_probability'] < .5:
                counter['validity_blocked_structurally_valid']+=1
                counter_cases['validity_blocked_structurally_valid'].append(rec['case_id'])
        typed_key='typed_play' if rec['typed_index']==0 else 'typed_not_play'
        for lang in ('all',rec['language_tag'],typed_key,rec['language_tag']+'_'+typed_key):
            if lang not in structure: continue
            x=structure[lang];n=geo['begin_count']
            x['zero_begin' if n==0 else 'one_begin' if n==1 else 'multiple_begin']+=1
            x['any_inside']+=int(geo['any_inside']);x['orphan_inside']+=int(geo['orphan_inside'])
            x['one_contiguous_run']+=int(geo['run_count']==1)
            x['multiple_runs']+=int(geo['run_count']>1)
            x['s3_track_emitted']+=int(pred['track'] is not None)
            x['s3_track_exact']+=int(pred['track']==prior.gold(row)['track'])
            x['s3_track_non_exact']+=int(pred['track'] is not None and pred['track']!=prior.gold(row)['track'])
    require(sum(track_matrix[x]['valid_track']+track_matrix[x]['invalid_or_missing_track'] for x in track_matrix)==300
        and counter['structurally_invalid_or_missing_track']+counter['structurally_valid_track']==70,DATA,'overlap_totals')
    typed={'gold_play':distribution(play),'gold_unknown':distribution(unknown)}
    typed['slices']={lang:{'gold_play':distribution([r for r in play if r['language_tag']==lang]),
        'gold_unknown':distribution([r for r in unknown if r['language_tag']==lang])} for lang in ('mixed','en')}
    typed['overlap']={'highest_unknown_probability':typed['gold_unknown']['max'],
        'lowest_play_probability':typed['gold_play']['min'],
        'median_unknown':typed['gold_unknown']['quantiles']['p50'],
        'median_play':typed['gold_play']['quantiles']['p50'],
        'play_below_0_5':typed['gold_play']['below_0_5'],
        'unknown_at_or_above_0_5':typed['gold_unknown']['at_or_above_0_5']}
    report={'bio_label_mapping':dict(enumerate(LABELS)),
        'bio_confusion':{lang:confusion([r for r in play if lang=='all' or r['language_tag']==lang])
            for lang in ('all','mixed','en')},
        'gold_span_coverage':{slot:{lang:span_coverage([r for r in play if lang=='all' or r['language_tag']==lang],slot,
            {r.case_id:r for r in rows})
            for lang in ('all','mixed','en')} for slot in SLOTS},
        'track_taxonomy':{'ordered_precedence':TAXONOMY_ORDER,'case_ids_by_category':classified,
            'counts':{k:len(v) for k,v in classified.items()},'machine_checkable_traces':traces,
            'pr88_exact_case_id_set_equal':set(traces)==set(taxonomy_ids),'total':218},
        'track_prediction_structure':structure,
        'typed_gate_counterfactual':{'label':'COUNTERFACTUAL_DIAGNOSTIC_ONLY',
            'structural_definition':'typed forced play, validity forced 1.0; no model forward',
            'typed_only_definition':'typed forced play, actual validity gate preserved; no model forward',
            'exact_pr88_case_id_set_equal':set(typed_ids)==set(counter_cases['structurally_invalid_or_missing_track']+counter_cases['structurally_valid_track']),
            'counts':counter,'case_ids':counter_cases},
        'typed_probability_distributions':typed,'typed_vs_span_overlap_matrix':track_matrix}
    report['adaptation_target_evidence']={'dominant_failure_category':'s3_track_invalid_or_missing',
        'dominant_failure_count':218,'typed_failure_count':70,'track_invalid_missing_count':218,
        'track_taxonomy_counts':report['track_taxonomy']['counts'],
        'typed_span_overlap_matrix':track_matrix,
        'optional_slot_failure_summary':{slot:report['gold_span_coverage'][slot]['all'] for slot in ('artist','album')},
        'authorization':False}
    return report


def child() -> tuple[dict[str, Any], Audit]:
    guard = Audit()
    sys.addaudithook(guard)
    counts = dict(live_invocations=1, model_load_attempts=0, model_loads=0, checkpoint_load_attempts=0,
        checkpoint_loads=0, validation_passes=0, validation_forward_batches=0, shared_model_decisions=0,
        historical_decoder_calls=0, s3_decoder_calls=0, additional_model_forwards_for_second_decoder=0,
        training_steps=0, backward_calls=0, optimizer_constructed=False, scheduler_constructed=False)
    result = {'schema': 'laya-span-typed-diagnosis-v1', 'status': BLOCKER,
        'NON_ACCEPTANCE_DIAGNOSTIC_ONLY': True, 'repo_base': BASE, 'task_scoped_compute_authorization': AUTHORIZATION,
        'authority_flags': dict(prior.audit.FLAGS), 'persistent_training_authorized': False,
        'persistent_model_compute_authorized': False, 'runner_sha256': sha(Path(__file__)),
        'scratch_created': True, 'scratch_namespace': 'diagnostic_scratch', 'cache_bindings': CACHE_BINDINGS,
        'execution_counts': counts, 'vram': {}, 'runtime_seconds': {}}
    before, hook = None, None
    try:
        require(os.environ.get('LAYA_SPAN_TYPED_TASK') == AUTHORIZATION
            and os.environ.get('LAYA_SPAN_TYPED_SHA') == result['runner_sha256'], BLOCKER, 'task_source_binding')
        require(os.environ.get('GIT_OPTIONAL_LOCKS') == '0', BLOCKER, 'git_optional_locks')
        require(not prior.git('status', '--porcelain'), BLOCKER, 'dirty_pre_live_commit')
        result['pre_live_commit'] = prior.git('rev-parse', 'HEAD')
        require(not RESULT.exists(), BLOCKER, 'durable_result_preexists')
        scratch_safe()
        require(SCRATCH.is_dir() and all(os.environ.get(key) == str(SCRATCH / value) for key, value in CACHE_BINDINGS.items()), BLOCKER, 'scratch_environment')
        before, all_rows, accepted, pr88 = identities()
        result['identities_before'] = before
        rows = historical.eligible_rows(all_rows, 540, 60)
        result['eligible_case_ids'] = [r.case_id for r in rows]
        result['blocked_case_ids'] = [r.case_id for r in all_rows if r.ai_scope != 'supported']
        guard.stage = 'dependency_import'
        import torch
        from transformers import AutoTokenizer
        require(torch.__version__ == '2.13.0+rocm10.0.0' and torch.version.hip == '7.15.26333'
            and torch.version.cuda is None, BLOCKER, 'torch_build')
        devices = [vars(d) for d in pinned.enumerate_accelerators(torch)]
        device = prior.select_device(devices)
        result.update(visible_devices=devices, selected_device=device)
        target = torch.device(device)
        torch.cuda.set_device(target)
        require(torch.cuda.current_device() == 1, prior.DEVICE, 'current_device')
        torch.cuda.reset_peak_memory_stats(target)
        result['vram']['baseline'] = smoke.vram(torch, target)
        sys.path.insert(0, str(pinned.SOURCE))
        import laya
        from laya.common import build_sequence
        require(Path(laya.__file__).resolve() == pinned.SOURCE / 'laya/__init__.py', prior.SOURCE, 'pinned_import')
        config = json.loads((pinned.MODEL / 'rl_agent_config.json').read_bytes())
        tokenizer = AutoTokenizer.from_pretrained(pinned.MODEL / 'tokenizer', local_files_only=True)
        items = historical.render(rows, tokenizer, build_sequence, config)
        result['renderer_equivalent_rows'] = len(items)
        guard.check()
        guard.stage = 'base_model_load'
        started = time.perf_counter()
        counts['model_load_attempts'] += 1
        agent = laya.load(str(pinned.MODEL), device='cuda:1')
        counts['model_loads'] += 1
        guard.check()
        torch.cuda.synchronize(target)
        result['runtime_seconds']['base_model_load'] = time.perf_counter() - started
        result['residency'] = pinned.residency(agent, device)
        result['cpu_fallback'] = result['residency']['cpu_fallback']
        model = agent.model
        del agent
        result['vram']['after_base_load'] = smoke.vram(torch, target)
        span, validity = smoke.new_heads(model, device, torch)
        guard.stage = 'checkpoint_restore'
        guard.check()
        started = time.perf_counter()
        counts['checkpoint_load_attempts'] += 1
        payload = torch.load(prior.CHECKPOINT_PATH, map_location='cpu', weights_only=True)
        counts['checkpoint_loads'] += 1
        guard.check()
        prior.validate_payload(payload, prior.checkpoint_binding(accepted))
        result['restored_parameter_hashes'] = prior.restore(payload, model, span, validity, torch)
        del payload
        for module in (model, span, validity):
            module.eval()
            module.requires_grad_(False)
        require(all(str(p.device) == device and not p.requires_grad for m in (model, span, validity) for p in m.parameters()), prior.RESTORE, 'device_or_freeze')
        result['checkpoint_restore'] = {'schema': 'laya-small-adaptation-final-v1', 'completed_steps': 189,
            'exact_keys_binding_verified': True, 'optimizer_payload': 'ignored', 'contains_frozen_weights': False}
        result['runtime_seconds']['checkpoint_load_restore'] = time.perf_counter() - started
        result['vram']['after_restore'] = smoke.vram(torch, target)
        captured = []
        hook = model.encoder.register_forward_hook(lambda _m, _a, output: captured.append(output.last_hidden_state))
        guard.stage = 'validation'
        torch.cuda.reset_peak_memory_stats(target)
        started = time.perf_counter()
        def infer(batch_items):
            guard.check()
            require(all(not m.training for m in (model, span, validity)), BLOCKER, 'eval_mode')
            with torch.no_grad():
                _, outputs = historical.forward(model, span, validity, batch_items, tokenizer.pad_token_id, device, captured, torch)
                typed = outputs['typed_logits'].float().argmax(-1).tolist()
                probability = outputs['typed_logits'].float().softmax(-1)[:, 0].tolist()
                validity_probability = outputs['validity_logits'].float().sigmoid().tolist()
                labels = outputs['span_logits'].argmax(-1).tolist()
            return typed, probability, validity_probability, labels
        old, new, decisions, token_records = validation_pass(result, rows, items, infer, guard)
        guard.check()
        torch.cuda.synchronize(target)
        result['runtime_seconds']['validation_wall'] = time.perf_counter() - started
        result['vram']['validation_peak'] = smoke.vram(torch, target)
        result['parameter_hashes_after'] = smoke.group_hashes(model, span, validity)
        require(result['parameter_hashes_after'] == prior.PARAMETERS, prior.RESTORE, 'after_validation')
        result['vram']['final'] = smoke.vram(torch, target)
        result['pr88_reproduction'] = reproduce(rows,old,new,decisions,pr88)
        result['historical'] = prior.report(rows, old, decisions)
        result['historical_reproduction'] = prior.reproduction(result['historical'], accepted['validation'])
        result['s3'] = prior.report(rows, new, decisions)
        require(prior.safety(result['s3']), DATA, 'safety')
        result['safety_gate_passed'] = True
        result['shared_decisions'] = decisions
        current_analysis = prior.analysis(rows,old,new,decisions)
        require(current_analysis['play_failure_case_ids']==pr88['analysis']['play_failure_case_ids'],
            REPRODUCTION,'pr88_failure_bucket_membership')
        result['pr88_failure_counts'] = current_analysis['play_failure_counts']
        result['token_records'] = token_records
        result['diagnosis'] = diagnose(rows,token_records,new,pr88)
        counts['structural_decoder_calls'] = 300
        counts['typed_only_counterfactual_decoder_calls'] = 70
        sanitization_check(result,[r.utterance for r in all_rows])
        result['status'] = PASS
    except Exception as exc:
        result.update(failure_record(exc), exception=exception_record(exc, guard.stage))
    finally:
        if hook is not None:
            hook.remove()
        guard.stage = 'post_identity'
        if before is not None:
            try:
                after, _, _, _ = identities()
                result['identities_after'] = after
                require(before == after, prior.SOURCE, 'protected_identity_changed')
            except Exception as exc:
                result.update(failure_record(exc), post_identity_exception=exception_record(exc, guard.stage))
        guard.stage = 'dependency_exit'
    return result, guard


def finish_child(result: dict[str, Any], guard: Audit) -> None:
    result['audit'] = guard.summary()
    result['process_boundary'] = {'utf8_mode': sys.flags.utf8_mode, 'dont_write_bytecode': sys.dont_write_bytecode,
        'offline': True, 'raw_byte_transport': True, 'git_optional_locks': '0',
        'allowed_reads': guard.allowed_reads, 'opened_row_sources': ['validation'] if guard.allowed_reads['validation'] else [],
        'train_opened': False, 'held_out_opened': False, 'stage_a_opened': False}
    if guard.first_denial:
        result['status'] = guard.first_denial['label']
    sanitization_check(result)
    result['canonical_result_sha256'] = canonical_hash(result)
    print(PREFIX + json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))


def scratch_inventory() -> list[dict[str, Any]]:
    scratch_safe()
    rows = []
    for path in sorted(SCRATCH.rglob('*')):
        require(not path.is_symlink() and not path.is_junction(), BLOCKER, 'scratch_inventory_redirected')
        if path.is_file():
            rows.append({'relative_path': path.relative_to(SCRATCH).as_posix(), 'size_bytes': path.stat().st_size, 'sha256': sha(path)})
    return rows


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve() and sys.flags.utf8_mode == 1, BLOCKER, 'parent_runtime')
    scratch_safe(absent=True)
    require(not RESULT.exists(), BLOCKER, 'durable_result_preexists')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update({key: str(SCRATCH / value) for key, value in CACHE_BINDINGS.items()})
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', GIT_OPTIONAL_LOCKS='0',
        LAYA_SPAN_TYPED_TASK=AUTHORIZATION, LAYA_SPAN_TYPED_SHA=sha(Path(__file__)))
    result = {'schema': 'laya-span-typed-diagnosis-v1', 'status': BLOCKER, 'repo_base': BASE,
        'NON_ACCEPTANCE_DIAGNOSTIC_ONLY': True, 'task_scoped_compute_authorization': AUTHORIZATION,
        'authority_flags': dict(prior.audit.FLAGS), 'runner_sha256': sha(Path(__file__)),
        'scratch_created': False, 'execution_counts': {'live_invocations': 0}}
    try:
        SCRATCH.mkdir(parents=True, exist_ok=False)
        result['scratch_created'] = True
        for relative in sorted(set(CACHE_BINDINGS.values())):
            (SCRATCH / relative).mkdir(parents=True, exist_ok=True)
        result['execution_counts'] = dict.fromkeys(('model_loads', 'checkpoint_loads', 'validation_passes',
            'validation_forward_batches', 'training_steps', 'backward_calls'), None)
        result['execution_counts']['live_invocations'] = 1
        completed = runner([str(pinned.PYTHON), '-B', '-X', 'utf8', str(Path(__file__).resolve()), '--child'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False, env=env, timeout=600)
        result['child_returncode'] = completed.returncode
        matches = [line[len(PREFIX):] for line in completed.stdout.decode('utf-8', 'strict').splitlines() if line.startswith(PREFIX)]
        require(len(matches) == 1, BLOCKER, 'child_result_missing_or_ambiguous')
        parsed = json.loads(matches[0])
        require(parsed.pop('canonical_result_sha256') == canonical_hash(parsed), BLOCKER, 'child_hash')
        require(parsed.get('scratch_created') is True and parsed.get('execution_counts', {}).get('live_invocations') == 1,
            BLOCKER, 'child_schema')
        result = parsed
        result['child_returncode'] = completed.returncode
        require(completed.returncode == 0, BLOCKER, 'child_exit')
    except Exception as exc:
        result.update(status=BLOCKER, transport_exception=exception_record(exc, 'parent_transport'))
    finally:
        if result['scratch_created']:
            try:
                result['scratch_inventory'] = scratch_inventory()
            except Exception as exc:
                result.update(status=BLOCKER, inventory_exception=exception_record(exc, 'parent_inventory'))
            result['scratch_cleaned'] = False
            try:
                scratch_safe()
                shutil.rmtree(SCRATCH)
                result['scratch_cleaned'] = not SCRATCH.exists()
            except Exception as exc:
                result['cleanup_exception'] = exception_record(exc, 'parent_cleanup')
            if not result['scratch_cleaned']:
                result['status'] = BLOCKER
    result['canonical_result_sha256'] = canonical_hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument('--preflight', action='store_true')
    options.add_argument('--validation-diagnostic', action='store_true')
    options.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        holder = []
        atexit.register(lambda: finish_child(*holder) if holder else None)
        holder.extend(child())
        return 0
    result = parent() if args.validation_diagnostic else preflight()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False))
    return 0 if result['status'] in (PASS, PREFLIGHT) else 1


if __name__ == '__main__':
    raise SystemExit(main())
