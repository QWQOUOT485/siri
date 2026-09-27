"""One task-scoped, read-only PR79 checkpoint diagnostic; no training entry point."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any

import local_ai_stage_b_laya_s3_research as research

historical, audit = research.historical, research.audit
smoke, pinned = historical.smoke, historical.pinned
ROOT = audit.ROOT
BASE = '6c1373dd9e7985616a76042756e7da2ddad16ade'
AUTHORIZATION = 'pr79-checkpoint-s3-validation-diagnostic-v1'
PASS = 'LAYA_PR79_CHECKPOINT_S3_VALIDATION_DIAGNOSTIC_PASSED'
DATA = 'STOP_LAYA_S3_DIAGNOSTIC_DATA_BOUNDARY'
SOURCE = 'STOP_LAYA_S3_DIAGNOSTIC_HISTORICAL_SOURCE_MUTATED'
CHECKPOINT = 'STOP_LAYA_PR79_DIAGNOSTIC_CHECKPOINT_IDENTITY'
RESTORE = 'STOP_LAYA_PR79_DIAGNOSTIC_RESTORE_MISMATCH'
DEVICE = 'STOP_LAYA_PR79_S3_DIAGNOSTIC_DEVICE_MISMATCH'
REPRODUCTION = 'STOP_LAYA_PR79_DIAGNOSTIC_REPRODUCTION_MISMATCH'
SAFETY = 'STOP_LAYA_S3_DIAGNOSTIC_SAFETY_REGRESSION'
BLOCKER = 'LAYA_PR79_S3_DIAGNOSTIC_NEW_BLOCKER'
PREFIX = 'LAYA_S3_PR79_DIAGNOSTIC='
PREFLIGHT = 'LAYA_PR79_S3_DIAGNOSTIC_PREFLIGHT_PASSED_NO_COMPUTE'
CHECKPOINT_PATH = Path(r'D:\ai\ai\stage_b_small_adaptation\6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a\final.pt')
CHECKPOINT_SHA = '199bfb8f1b0a3a3a930947b93e3df2f6214950e8cfacaa28b0aefb5fa7ec1a8d'
VALIDATION = ROOT / 'artifacts/local_ai/stage_b/final_v1/validation.jsonl'
RESULT = ROOT / 'docs/local_ai/stage_b/evidence/LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json'
SOURCES = {
 'local_ai_stage_b_laya_small_adaptation.py': '85832ab8a28780c93a0742db1db178f8458e536812f73181308f8057d9b2633e',
 'local_ai_stage_b_laya_adapter.py': 'cdda28ad4821d1c032d74ac23d6b0aba54f15d4f342616512d5a64faca751f8e',
 'local_ai_stage_b_laya_span_representability_audit.py': '6615121c5d4e637916777650e248ebff5a2e9380b45b4238702e4efe9d7d0087',
 'local_ai_stage_b_laya_span_seam_design.py': '7b739acf83bbf57db72ac79684fbe807eb3fd2b3ecc5e3e28c1324f150a5db72',
 'local_ai_stage_b_laya_span_decoder.py': 'f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845',
 'local_ai_stage_b_laya_span_seam_implementation_verify.py': '35203544303153cab0df03145bddb21a6c6f08f0d97f5b4f213cedfab115c3e2',
 'local_ai_stage_b_laya_s3_research.py': 'b01a254db9bfb1d84023c0f9d88ff7d49ccb789ff7888961ea7e000dfa2d4388'}
PARAMETERS = {
 'encoder': 'e158bfb1ff7d701715008e6247d4a2e99b94c8384281ccfb2629dfde2016e812',
 'act_head': '7568d33742b4239cec61ef3cd24ff533a342e8f1d98158ea7f997757efa0394d',
 'typed': 'a5c3f736e7c943ab39039eb240cf635df22521d74fe159a01f899d149816660b',
 'span': '864e146331b596e2d555ecc34cd4e968a0f3ee233721f5ebd3e18f72c23afd20',
 'validity': '9e339959e40062df3fda976970361f7fc53793ee5b616b6b01eea06b35bdb2aa'}
BUCKETS = ('typed_not_play', 'validity_below_threshold', 's3_track_invalid_or_missing',
 's3_track_present_not_exact', 's3_track_exact_optional_incomplete_or_wrong', 'full_semantic_exact')
TRANSITIONS = ('unchanged_unknown', 'unchanged_play_exact_same_offsets', 'unknown_to_play',
 'play_to_unknown', 'play_to_play_offsets_changed')
canonical_hash = audit.canonical_hash


def require(ok: bool, label: str, detail: str = '') -> None:
    if not ok:
        raise ValueError(label + (':' + detail if detail else ''))


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=ROOT, check=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).stdout.decode('ascii', 'strict').strip()


def source_identity() -> dict[str, str]:
    observed = {name: sha(ROOT / 'scripts' / name) for name in SOURCES}
    require(observed == SOURCES, SOURCE)
    return observed


def checkpoint_identity(path: Path = CHECKPOINT_PATH) -> dict[str, Any]:
    require(path == CHECKPOINT_PATH and path.is_file(), CHECKPOINT, 'path')
    for component in (path, *path.parents):
        info = component.lstat()
        require(not component.is_symlink() and not component.is_junction()
            and not info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, CHECKPOINT, 'redirected')
    info = path.stat()
    require(info.st_size == 177394599 and bool(info.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY), CHECKPOINT, 'size_or_readonly')
    digest = sha(path)
    require(digest == CHECKPOINT_SHA, CHECKPOINT, 'sha')
    return {'path': '<external-adaptation-root>/6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a/final.pt',
        'sha256': digest, 'size_bytes': info.st_size, 'readonly': True, 'redirected': False}


def read_guard(opened: set[str], denied: list[str]):
    """Install only in standalone CLI processes; deny protected rows and Python filesystem writes."""
    validation = str(VALIDATION.resolve()).casefold()
    protected = tuple(str((ROOT / p).resolve()).casefold() + os.sep for p in ('artifacts', 'tests/fixtures'))
    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event == 'os.mkdir' and Path(args[0]).is_dir() and not Path(args[0]).is_symlink() and not Path(args[0]).is_junction():
            # os.makedirs(exist_ok=True) issues mkdir first; an existing directory cannot be created.
            return
        if event in ('socket.connect', 'socket.getaddrinfo', 'os.remove', 'os.rename', 'os.rmdir',
                     'os.mkdir', 'os.chmod', 'os.link', 'os.symlink', 'os.truncate'):
            denied.append('network' if event.startswith('socket.') else 'blocked_write')
            raise PermissionError(DATA + ':network_or_write')
        if event != 'open' or not args:
            return
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            denied.append('write')
            raise PermissionError(DATA + ':write')
        if not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        key = str(path).casefold()
        if (key.startswith(protected) or path.name.casefold() in ('train.jsonl', 'held_out.jsonl', 'ai_intent_cases.json')) and key != validation:
            denied.append('protected_rows')
            raise PermissionError(DATA + ':protected_rows')
        if key == validation:
            opened.add('validation')
    return guard


def accepted_evidence() -> dict[str, Any]:
    return research.canonical_evidence('LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json', research.PR79_SHA)


def no_compute_identity() -> tuple[dict[str, Any], list[Any], dict[str, Any]]:
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve() and sys.version_info[:3] == (3, 14, 7), BLOCKER, 'python')
    require(sys.flags.utf8_mode == 1 and sys.dont_write_bytecode, BLOCKER, 'process_flags')
    require(all(os.environ.get(k) == '1' for k in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'))
        and not os.environ.get('PYTHONPATH'), BLOCKER, 'offline_environment')
    require(git('rev-parse', 'origin/main') == git('merge-base', 'HEAD', BASE) == BASE, 'STOP_REVIEWED_STATE_CHANGED')
    packages = {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'safetensors', 'huggingface-hub', 'numpy')}
    require(packages == {'torch': '2.13.0+rocm10.0.0', 'transformers': '4.57.6', 'safetensors': '0.7.0', 'huggingface-hub': '0.36.2', 'numpy': '2.3.5'}, BLOCKER, 'packages')
    inventory = pinned.package_inventory()
    require(inventory == '3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337', BLOCKER, 'inventory')
    prior = accepted_evidence()
    try:
        rows = historical.parse_validation(VALIDATION.read_bytes())
        composition = historical.validate_validation(rows)
    except Exception as exc:
        raise ValueError(DATA + ':validation_identity_or_schema') from exc
    report79 = ROOT / 'docs/local_ai/stage_b/evidence/LOCAL_AI_STAGE_B_LAYA_SMALL_ADAPTATION_2026-09-26.md'
    identity = {'sources': source_identity(), 'runner_sha256': sha(Path(__file__)),
        'source_revision': pinned.source_identity(), 'packages': packages, 'venv_sha256': inventory,
        'tokenizer': audit.tokenizer_identity(), 'checkpoint': checkpoint_identity(),
        'validation_sha256': sha(VALIDATION), 'validation_composition': composition,
        'pr79_canonical_sha256': research.PR79_SHA, 'pr79_json_byte_sha256': sha(audit.RESULT79),
        'pr79_report_byte_sha256': sha(report79)}
    require(prior['parameter_hashes_after'] == PARAMETERS, RESTORE, 'reviewed_evidence')
    return identity, rows, prior


def preflight() -> dict[str, Any]:
    identity, _, _ = no_compute_identity()
    require(not RESULT.exists(), BLOCKER, 'durable_result_already_exists')
    return {'status': PREFLIGHT, 'repo_base': BASE, 'identity': identity,
        'model_loads': 0, 'checkpoint_loads': 0, 'validation_passes': 0,
        'authority_flags': dict(audit.FLAGS)}


def select_device(devices: list[dict[str, Any]]) -> str:
    require([(d['index'], d['name'], d['architecture']) for d in devices] == [
        (0, 'AMD Radeon(TM) Graphics', 'gfx1036'), (1, 'AMD Radeon RX 9070 XT', 'gfx1201')]
        and all(d['device_type'] == 'cuda' and d['total_memory_bytes'] > 0 for d in devices), DEVICE)
    return 'cuda:1'


def checkpoint_binding(prior: dict[str, Any]) -> dict[str, Any]:
    return {'config': json.loads(json.dumps(historical.CONFIG)), 'seed': 1729,
        'train_selection': prior['selection'], 'identities': prior['identities_before']}


def validate_payload(payload: Any, binding: dict[str, Any]) -> None:
    require(isinstance(payload, dict) and set(payload) == historical.CHECKPOINT_KEYS
        and payload['schema'] == 'laya-small-adaptation-final-v1'
        and type(payload['completed_steps']) is int and payload['completed_steps'] == 189
        and payload['binding'] == binding, CHECKPOINT, 'schema_keys_binding_step')


def restore(payload: dict[str, Any], model: Any, span: Any, validity: Any, torch: Any) -> dict[str, str]:
    typed = smoke.parameter_groups(model, span, validity)['typed']
    for name, current in (('typed', typed), ('span', span.state_dict()), ('validity', validity.state_dict())):
        require(isinstance(payload[name], dict) and set(payload[name]) == set(current), RESTORE, 'keys')
        for key, value in current.items():
            saved = payload[name][key]
            require(isinstance(saved, torch.Tensor) and saved.shape == value.shape and saved.dtype == value.dtype
                and str(saved.device) == 'cpu' and bool(torch.isfinite(saved).all()), RESTORE, 'tensor')
    with torch.no_grad():
        for name, parameter in typed.items():
            parameter.copy_(payload['typed'][name])
    span.load_state_dict(payload['span'], strict=True)
    validity.load_state_dict(payload['validity'], strict=True)
    hashes = smoke.group_hashes(model, span, validity)
    require(hashes == PARAMETERS, RESTORE, 'hashes')
    return hashes


def dual_decode(rows: list[Any], items: list[dict[str, Any]], typed: list[int], probs: list[float],
                valid: list[float], tags: list[list[int]]) -> tuple[list[Any], list[Any], list[Any]]:
    require(len(rows) == len(items) == len(typed) == len(probs) == len(valid) == len(tags)
        and all(r.ai_scope == 'supported' for r in rows), DATA, 'eligibility_or_output_length')
    old, new, decisions = [], [], []
    for row, item, index, probability, validity, labels in zip(rows, items, typed, probs, valid, tags):
        mask = item['user_state_mask']
        require(len(labels) >= len(mask), BLOCKER, 'labels_short')
        labels = [label if inside else 0 for label, inside in zip(labels, mask)]
        args = (index, validity, labels, mask, item['token_offsets'], row.utterance)
        old.append(historical.decode(*args))
        new.append(research.validation_decode(*args))
        decisions.append({'case_id': row.case_id, 'typed_index': index,
            'typed_play_probability': probability, 'validity_probability': validity})
    return old, new, decisions


def safety(report: dict[str, Any]) -> bool:
    return (report['supported_unknown_recall'] == historical.rate(240, 240)
        and report['unknown_false_acceptance'] == historical.rate(0, 240)
        and report['blocked_before_renderer'] == historical.rate(60, 60)
        and report['eligibility_leakage'] == 0 and report['predicted_play_without_valid_track'] == 0)


def report(rows: list[Any], predictions: list[Any], decisions: list[Any]) -> dict[str, Any]:
    value = historical.metrics(rows, predictions)
    value.update(blocked_before_renderer=historical.rate(60, 60), eligibility_leakage=0,
        model_rows=len(rows), case_ids=[r.case_id for r in rows])
    value['slices'] = {lang: historical.metrics([r for r in rows if r.language_tag == lang],
        [p for r, p in zip(rows, predictions) if r.language_tag == lang]) for lang in ('mixed', 'en')}
    value['uncalibrated_confidence'] = {}
    for expected in ('spotify_play_track', 'unknown'):
        values = [d for r, d in zip(rows, decisions) if r.expected.intent == expected]
        value['uncalibrated_confidence'][expected] = {key: {'min': min(c[key] for c in values),
            'max': max(c[key] for c in values), 'mean': sum(c[key] for c in values) / len(values)}
            for key in ('typed_play_probability', 'validity_probability')}
    value['predictions'] = [{'case_id': r.case_id, **p} for r, p in zip(rows, predictions)]
    value['safety_triage_passed'] = safety(value)
    return value


def reproduction(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    mismatches = [a['case_id'] for a, b in zip(actual['predictions'], expected['predictions']) if a != b]
    metric_keys = set(expected) - {'predictions', 'uncalibrated_confidence'}
    equal = set(actual) == set(expected) and all(actual[k] == expected[k] for k in metric_keys)
    proof = {'prediction_rows': len(actual['predictions']), 'exact_matches': len(actual['predictions']) - len(mismatches),
        'mismatch_case_ids': mismatches, 'aggregate_metrics_equal': equal,
        'confidence_summaries_equal': actual['uncalibrated_confidence'] == expected['uncalibrated_confidence']}
    require(len(actual['predictions']) == len(expected['predictions']) == 540 and not mismatches and equal, REPRODUCTION)
    return proof


def transition(old: dict[str, Any], new: dict[str, Any]) -> str:
    if old['intent'] == 'unknown':
        return 'unchanged_unknown' if new['intent'] == 'unknown' else 'unknown_to_play'
    if new['intent'] == 'unknown':
        return 'play_to_unknown'
    return 'unchanged_play_exact_same_offsets' if old == new else 'play_to_play_offsets_changed'


def gold(row: Any) -> dict[str, Any]:
    return {slot: audit.raw_span(getattr(row.expected, slot)) for slot in audit.SLOTS}


def failure(row: Any, prediction: dict[str, Any], decision: dict[str, Any]) -> str:
    expected = gold(row)
    if decision['typed_index'] != 0:
        return BUCKETS[0]
    if decision['validity_probability'] < .5:
        return BUCKETS[1]
    if prediction['track'] is None:
        return BUCKETS[2]
    if prediction['track'] != expected['track']:
        return BUCKETS[3]
    if any(prediction[s] != expected[s] for s in ('artist', 'album')):
        return BUCKETS[4]
    return BUCKETS[5]


def analysis(rows: list[Any], old: list[Any], new: list[Any], decisions: list[Any]) -> dict[str, Any]:
    transitions = {key: [] for key in TRANSITIONS}
    buckets = {key: [] for key in BUCKETS}
    slices = {lang: dict.fromkeys(BUCKETS, 0) for lang in ('mixed', 'en')}
    slots = {s: {'presence': 0, 'exact': 0, 'start_delta': Counter(), 'end_delta': Counter(),
        'pure_leading_whitespace_corrections': [], 'newly_exact': [], 'non_exact': []} for s in audit.SLOTS}
    cross = []
    play_transitions = dict.fromkeys(('historical_unknown_to_s3_play', 'historical_play_to_s3_play',
                                     'historical_play_to_s3_unknown', 'unchanged_unknown'), 0)
    unknown_errors = []
    for row, before, after, decision in zip(rows, old, new, decisions):
        expected = gold(row)
        entry = {'case_id': row.case_id, 'historical': before, 's3': after, 'gold': expected}
        transitions[transition(before, after)].append(entry)
        if before['intent'] == 'play':
            cross.append({**entry, 'changed': before != after, 'track_became_exact': before['track'] != expected['track'] == after['track'],
                'optional_slots_changed': [s for s in ('artist', 'album') if before[s] != after[s]]})
        if row.expected.intent == 'unknown':
            if after['intent'] != 'unknown':
                unknown_errors.append(row.case_id)
            continue
        key = failure(row, after, decision)
        buckets[key].append(row.case_id)
        if row.language_tag in slices:
            slices[row.language_tag][key] += 1
        old_play, new_play = before['intent'] != 'unknown', after['intent'] != 'unknown'
        play_transitions[('historical_play_to_s3_play' if new_play else 'historical_play_to_s3_unknown') if old_play
            else ('historical_unknown_to_s3_play' if new_play else 'unchanged_unknown')] += 1
        for slot in audit.SLOTS:
            observed, target, prior = after[slot], expected[slot], before[slot]
            if observed is None:
                continue
            summary = slots[slot]
            summary['presence'] += 1
            detail = {'case_id': row.case_id, 'historical': prior, 's3': observed, 'gold': target}
            if target is not None:
                summary['start_delta'][str(observed['start'] - target['start'])] += 1
                summary['end_delta'][str(observed['end'] - target['end'])] += 1
            if observed == target:
                summary['exact'] += 1
                if prior != target:
                    summary['newly_exact'].append(detail)
            else:
                summary['non_exact'].append(detail)
            if prior and prior['end'] == observed['end'] and prior['start'] < observed['start'] and row.utterance[prior['start']:observed['start']].isspace():
                summary['pure_leading_whitespace_corrections'].append(row.case_id)
    require(sum(map(len, buckets.values())) == 300 and len(cross) == 11, REPRODUCTION, 'analysis_denominators')
    ceiling = {'track': 297, 'artist': 126, 'album': 203}
    return {'transition_counts': {k: len(v) for k, v in transitions.items()}, 'transitions': transitions,
        'gold_play_transitions': play_transitions, 'unknown_rows': 240, 'unknown_safety_error_ids': unknown_errors,
        'play_failure_counts': {k: len(v) for k, v in buckets.items()}, 'play_failure_case_ids': buckets,
        'failure_slices': slices, 'slots': slots, 'historical_eleven_plays': cross,
        'structural_oracle_gap': {s: {'learned_exact': slots[s]['exact'], 'gold_bio_ceiling': ceiling[s],
            'gap': ceiling[s] - slots[s]['exact']} for s in audit.SLOTS}}


def model_identity() -> dict[str, Any]:
    rows, aggregate = pinned.artifact_inventory()
    pinned.model_identity(rows, aggregate)
    return {'aggregate_sha256': aggregate, 'files': rows}


def child() -> dict[str, Any]:
    counts = dict(live_invocations=1, model_loads=0, checkpoint_loads=0, validation_passes=0,
        validation_forward_batches=0, shared_model_decisions=0, historical_decoder_calls=0, s3_decoder_calls=0,
        additional_model_forwards_for_second_decoder=0, training_steps=0, backward_calls=0, optimizer_constructed=False)
    result = {'schema': 'laya-s3-pr79-validation-diagnostic-v1', 'status': BLOCKER, 'repo_base': BASE,
        'NON_ACCEPTANCE_DIAGNOSTIC_ONLY': True, 'task_scoped_compute_authorization': AUTHORIZATION,
        'persistent_model_compute_authorized': False, 'persistent_training_authorized': False,
        'authority_flags': dict(audit.FLAGS), 'execution_counts': counts, 'vram': {}, 'runtime_seconds': {}}
    opened, denied, hook, before = set(), [], None, None
    sys.addaudithook(read_guard(opened, denied))
    try:
        require(os.environ.get('LAYA_DIAGNOSTIC_TASK') == AUTHORIZATION, BLOCKER, 'task_authorization')
        require(os.environ.get('LAYA_DIAGNOSTIC_RUNNER_SHA') == sha(Path(__file__)), SOURCE, 'runner')
        require(not RESULT.exists(), BLOCKER, 'durable_result_already_exists')
        before, all_rows, prior = no_compute_identity()
        result['identities_before'] = before
        result['prelive_commit'] = git('rev-parse', 'HEAD')
        require(not git('status', '--porcelain'), BLOCKER, 'uncommitted_prelive_source')
        rows = historical.eligible_rows(all_rows, 540, 60)
        result['blocked_case_ids'] = [r.case_id for r in all_rows if r.ai_scope != 'supported']
        result['eligible_case_ids'] = [r.case_id for r in rows]
        result['model_before'] = model_identity()
        import torch
        from transformers import AutoTokenizer
        require(torch.__version__ == '2.13.0+rocm10.0.0' and torch.version.hip == '7.15.26333', BLOCKER, 'torch_hip')
        devices = [vars(d) for d in smoke.enumerate_accelerators(torch)]
        device = select_device(devices)
        result.update(visible_devices=devices, selected_device=device, cpu_fallback=False)
        target = torch.device(device)
        torch.cuda.set_device(target)
        require(torch.cuda.current_device() == 1, DEVICE, 'current_device')
        torch.cuda.reset_peak_memory_stats(target)
        result['vram']['baseline'] = smoke.vram(torch, target)
        sys.path.insert(0, str(pinned.SOURCE))
        import laya
        from laya.common import build_sequence
        require(Path(laya.__file__).resolve() == (pinned.SOURCE / 'laya/__init__.py').resolve(), SOURCE, 'laya_import')
        config = json.loads((pinned.MODEL / 'rl_agent_config.json').read_bytes())
        tokenizer = AutoTokenizer.from_pretrained(pinned.MODEL / 'tokenizer', local_files_only=True)
        rendered = historical.render(rows, tokenizer, build_sequence, config)
        result['renderer_equivalent_rows'] = len(rendered)
        result['base_state_header'] = pinned.validate_checkpoint_header(pinned.checkpoint_header())
        started = time.perf_counter()
        counts['model_loads'] += 1
        agent = laya.load(str(pinned.MODEL), device=device)
        result['runtime_seconds']['model_load'] = time.perf_counter() - started
        result['residency'] = pinned.residency(agent, device)
        model = agent.model
        del agent
        span, validity = smoke.new_heads(model, device, torch)
        result['vram']['after_base_load'] = smoke.vram(torch, target)
        started = time.perf_counter()
        counts['checkpoint_loads'] += 1
        payload = torch.load(CHECKPOINT_PATH, map_location='cpu', weights_only=True)
        validate_payload(payload, checkpoint_binding(prior))
        result['restored_parameter_hashes'] = restore(payload, model, span, validity, torch)
        del payload
        result['checkpoint_schema'] = 'laya-small-adaptation-final-v1'
        result['checkpoint_completed_steps'] = 189
        result['checkpoint_contains_frozen_weights'] = False
        for module in (model, span, validity):
            module.eval()
            module.requires_grad_(False)
        require(all(str(p.device) == device and not p.requires_grad for m in (model, span, validity) for p in m.parameters()), RESTORE, 'residency_or_freeze')
        result['runtime_seconds']['checkpoint_load_restore'] = time.perf_counter() - started
        result['vram']['after_checkpoint_restore'] = smoke.vram(torch, target)
        captured = []
        hook = model.encoder.register_forward_hook(lambda _m, _a, output: captured.append(output.last_hidden_state))
        old, new, decisions = [], [], []
        counts['validation_passes'] += 1
        torch.cuda.reset_peak_memory_stats(target)
        started = time.perf_counter()
        batches = []
        for start in range(0, 540, 16):
            batch_rows, items = rows[start:start + 16], rendered[start:start + 16]
            require(all(r.ai_scope == 'supported' for r in batch_rows), DATA, 'before_forward')
            require(all(not m.training for m in (model, span, validity)), BLOCKER, 'eval')
            with torch.no_grad():
                counts['validation_forward_batches'] += 1
                _, outputs = historical.forward(model, span, validity, items, tokenizer.pad_token_id, device, captured, torch)
                typed = outputs['typed_logits'].float().argmax(-1).tolist()
                probs = outputs['typed_logits'].float().softmax(-1)[:, 0].tolist()
                valid = outputs['validity_logits'].float().sigmoid().tolist()
                tags = outputs['span_logits'].argmax(-1).tolist()
            a, b, c = dual_decode(batch_rows, items, typed, probs, valid, tags)
            old.extend(a); new.extend(b); decisions.extend(c)
            for key in ('shared_model_decisions', 'historical_decoder_calls', 's3_decoder_calls'):
                counts[key] += len(batch_rows)
            batches.append([r.case_id for r in batch_rows])
        torch.cuda.synchronize(target)
        result['runtime_seconds']['validation_wall'] = time.perf_counter() - started
        result['vram']['validation_peak'] = smoke.vram(torch, target)
        result['batch_case_ids'] = batches
        require([len(b) for b in batches] == [16] * 33 + [12], DATA, 'batch_count')
        result['parameter_hashes_after'] = smoke.group_hashes(model, span, validity)
        require(result['parameter_hashes_after'] == PARAMETERS, RESTORE, 'after_validation')
        result['vram']['final'] = smoke.vram(torch, target)
        result['historical'] = report(rows, old, decisions)
        result['historical_reproduction'] = reproduction(result['historical'], prior['validation'])
        result['s3'] = report(rows, new, decisions)
        require(safety(result['s3']), SAFETY)
        result['shared_decisions'] = decisions
        result['analysis'] = analysis(rows, old, new, decisions)
        result['status'] = PASS
    except Exception as exc:
        reason = str(exc)
        label = reason.split(':', 1)[0]
        result.update(status=label if label in (DATA, SOURCE, CHECKPOINT, RESTORE, DEVICE, REPRODUCTION, SAFETY, 'STOP_REVIEWED_STATE_CHANGED') else BLOCKER,
            blocker=reason if isinstance(exc, (ValueError, PermissionError, pinned.GateError)) else type(exc).__name__)
    finally:
        if hook is not None:
            hook.remove()
        if before is not None:
            try:
                after, _, _ = no_compute_identity()
                result['identities_after'] = after
                require(after == before, SOURCE, 'post_identity_changed')
                if 'model_before' in result:
                    result['model_after'] = model_identity()
                    require(result['model_after'] == result['model_before'], SOURCE, 'model_changed')
            except Exception as exc:
                result.update(status=SOURCE, blocker=str(exc) if isinstance(exc, ValueError) else type(exc).__name__)
        result['process_boundary'] = {'utf8_mode': sys.flags.utf8_mode, 'dont_write_bytecode': sys.dont_write_bytecode,
            'offline': True, 'raw_byte_transport': True, 'opened_row_sources': sorted(opened), 'denied_operations': dict(Counter(denied)),
            'train_rows_opened': False, 'held_out_rows_opened': False, 'stage_a_rows_opened': False,
            'python_filesystem_writes_allowed': False, 'optimizer_payload': 'ignored; no optimizer constructed or loaded'}
        if any(event in ('network', 'protected_rows') for event in denied):
            result.update(status=DATA, blocker='denied_protected_data_or_network_operation')
    result['canonical_result_sha256'] = canonical_hash(result)
    return result


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    preflight()
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        TORCHINDUCTOR_CACHE_DIR=str(Path(os.environ['LOCALAPPDATA']) / 'Temp/torchinductor_user'), LAYA_DIAGNOSTIC_TASK=AUTHORIZATION,
        LAYA_DIAGNOSTIC_RUNNER_SHA=sha(Path(__file__)))
    completed = runner([str(pinned.PYTHON), '-B', '-X', 'utf8', str(Path(__file__).resolve()), '--child'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False, env=env, timeout=1800)
    matches = [line[len(PREFIX):] for line in completed.stdout.decode('utf-8', 'strict').splitlines() if line.startswith(PREFIX)]
    require(len(matches) == 1, BLOCKER, 'child_result_missing_or_ambiguous')
    result = json.loads(matches[0])
    unsigned = dict(result)
    require(unsigned.pop('canonical_result_sha256') == canonical_hash(unsigned), BLOCKER, 'result_hash')
    require((result['status'] == PASS) == (completed.returncode == 0), BLOCKER, 'child_exit')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--preflight', action='store_true')
    group.add_argument('--validation-diagnostic', action='store_true')
    group.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        result = child()
    else:
        if not args.validation_diagnostic:
            sys.addaudithook(read_guard(set(), []))
        result = parent() if args.validation_diagnostic else preflight()
    print((PREFIX if args.child else '') + json.dumps(result, ensure_ascii=True, sort_keys=True, indent=None if args.child else 2, allow_nan=False))
    return 0 if result['status'] in (PASS, PREFLIGHT) else 1


if __name__ == '__main__':
    raise SystemExit(main())

