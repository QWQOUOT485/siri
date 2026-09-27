"""Versioned S3 research wiring. This CLI only performs no-compute preflight."""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import local_ai_stage_b_laya_small_adaptation as historical
import local_ai_stage_b_laya_span_decoder as s3_decoder
import local_ai_stage_b_laya_span_representability_audit as audit

BASE = 'c3f863f006356db2e179ea7f4207ac099effa604'
PATH_VERSION = 'laya-s3-research-v1'
DECODER_VERSION = 'reviewed-s3-span-decoder-v1'
FUTURE_RESULT_SCHEMA = 'laya-s3-research-result-v1'
FUTURE_CHECKPOINT_SCHEMA = 'laya-s3-research-checkpoint-v1'
FUTURE_CHECKPOINT_NAMESPACE = Path(r'D:\ai\ai\stage_b_laya_s3_research') / PATH_VERSION / BASE
IMPLEMENTATION_SHA = '08e8173175f5a879b7677cde2fdaedbc844ae5e4dc790b1d81bb174c46d4bcbb'
DECODER_SHA = 'f497267fdbf916a193191d64b0b59853fa7473a27a1a592c1ce47498bfafd845'
PR79_SHA = '4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8'
SELECTOR_SHA = 'fd69f3280becca6e12225d36960b016bd8e6e4bf9e3962e393c4bef0e0ff2c1d'
PASS = 'LAYA_S3_VERSIONED_RESEARCH_PATH_PREFLIGHT_PASSED'
AMBIGUOUS = 'STOP_LAYA_S3_RESEARCH_PATH_DECODER_AMBIGUOUS'
DRIFT = 'STOP_LAYA_S3_RESEARCH_PATH_RECIPE_DRIFT'
MUTATED = 'STOP_LAYA_S3_HISTORICAL_SOURCE_MUTATED'
BLOCKER = 'LAYA_S3_RESEARCH_PATH_NEW_BLOCKER'
RECIPE = {'seed': 1729, 'epochs': 3, 'batch_size': 8, 'drop_last': False,
    'steps_per_epoch': 63, 'optimizer_steps': 189, 'validation_batch_size': 16,
    'optimizer': {'name': 'AdamW', 'lr': 1e-4, 'weight_decay': 0.0,
                  'betas': [0.9, 0.999], 'eps': 1e-8, 'foreach': False},
    'scheduler': None, 'clip_max_norm': 1.0, 'validity_threshold': 0.5,
    'loss_weights': {'intent': 1.0, 'span': 1.0, 'validity': 1.0},
    'autocast': 'cuda bfloat16', 'loss_metric_dtype': 'float32', 'grad_scaler': False,
    'training_mode': 'trainable modules train; encoder and act_head eval', 'validation_passes': 1}


def validation_decode(typed_index: int, validity_probability: float, bio_labels: list[int],
                      user_state_mask: list[bool], offsets: list[Any], utterance: str) -> dict[str, Any]:
    """Future evaluation seam: mask non-user labels, then dispatch only to verified S3."""
    audit.require(len(bio_labels) == len(user_state_mask), BLOCKER + ':label_mask_length')
    labels = [label if inside else 0 for label, inside in zip(bio_labels, user_state_mask)]
    return s3_decoder.decode(typed_index, validity_probability, labels, user_state_mask, offsets, utterance)


def canonical_evidence(name: str, expected: str) -> dict[str, Any]:
    value = json.loads((audit.ROOT / 'docs/local_ai/stage_b/evidence' / name).read_bytes())
    audit.require(value.pop('canonical_result_sha256') == expected == audit.canonical_hash(value), BLOCKER + ':evidence_identity')
    return value


def historical_hashes(implementation: dict[str, Any]) -> dict[str, str]:
    expected = {**implementation['historical_before'], **implementation['source_hashes']}
    audit.require(len(expected) == 6 and expected['local_ai_stage_b_laya_span_decoder.py'] == DECODER_SHA, MUTATED)
    observed = {name: hashlib.sha256((audit.ROOT / 'scripts' / name).read_bytes()).hexdigest() for name in expected}
    audit.require(observed == expected and implementation['historical_before'] == implementation['historical_after'], MUTATED)
    return observed


def repo_identity() -> dict[str, str]:
    def git(*args: str) -> str:
        completed = subprocess.run(['git', *args], cwd=audit.ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return completed.stdout.decode('ascii', 'strict').strip()
    origin = git('rev-parse', 'origin/main')
    base = git('merge-base', 'HEAD', BASE)
    audit.require(origin == base == BASE, 'STOP_REVIEWED_STATE_CHANGED')
    return {'origin_main': origin, 'branch_base': base}


def flat(value: dict[str, Any], prefix: str = '') -> dict[str, Any]:
    result = {}
    for key, item in value.items():
        key = prefix + key
        if isinstance(item, dict):
            result.update(flat(item, key + '.'))
        else:
            result[key] = item
    return result


def recipe_audit(pr79: dict[str, Any]) -> dict[str, Any]:
    """Compare intended values with actual runner CONFIG and reviewed canonical evidence."""
    observed = json.loads(json.dumps(historical.CONFIG))
    evidence = pr79['config']
    audit.require(observed == evidence and observed['decoder'] == 'strict-grounded-bio-v1', DRIFT)
    intended = flat(RECIPE)
    source_values = flat({k: v for k, v in observed.items() if k != 'decoder'})
    evidence_values = flat({k: v for k, v in evidence.items() if k != 'decoder'})
    audit.require(audit.canonical_hash(intended) == audit.canonical_hash(source_values) == audit.canonical_hash(evidence_values), DRIFT)
    matrix = {key: {'intended': value, 'runner_config': source_values[key],
                    'reviewed_evidence': evidence_values[key], 'equal': True} for key, value in intended.items()}
    # Read source only: no optimizer/forward/mode helper is invoked here.
    snippets = {
        'encoder_eval': ('training_mode', 'model.encoder.eval()'),
        'act_head_eval': ('training_mode', 'model.act_head.eval()'),
        'freeze_policy_invoked': ('training_mode', 'smoke.freeze_policy(model)'),
        'optimizer_adamw': ('make_optimizer', 'torch.optim.AdamW(parameters, **smoke.OPTIMIZER_CONFIG)'),
        'optimizer_allowed_groups': ('make_optimizer', 'for k in ("typed", "span", "validity")'),
        'clip_1': ('update_step', 'clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True)'),
        'autocast_bf16': ('forward', 'torch.autocast(device_type="cuda", dtype=torch.bfloat16)')}
    source_checks = {}
    for key, (function, snippet) in snippets.items():
        source = inspect.getsource(getattr(historical, function))
        audit.require(snippet in source, DRIFT)
        source_checks[key] = {'verified': True, 'source_function': function}
    freeze_source = inspect.getsource(historical.smoke.freeze_policy)
    audit.require('parameter.requires_grad_(name.startswith(TYPED_PREFIXES))' in freeze_source
                  and historical.smoke.TYPED_PREFIXES == ('type_emb.', 'head.', 'scorer.'), DRIFT)
    names = pr79['parameter_names']
    audit.require(set(names) == {'encoder', 'act_head', 'typed', 'span', 'validity'}
        and all(n.startswith(historical.smoke.TYPED_PREFIXES) for n in names['typed'])
        and all(names[k] for k in names), DRIFT)
    audit.require(all(pr79['parameter_hashes_before'][k] == pr79['parameter_hashes_after'][k]
                      for k in ('encoder', 'act_head')), DRIFT)
    runner_tree = ast.parse(Path(historical.__file__).read_text(encoding='utf-8'))
    constructor_names = {n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
        for n in ast.walk(runner_tree) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))}
    audit.require(not constructor_names & {'GradScaler', 'LambdaLR', 'StepLR', 'CosineAnnealingLR'}, DRIFT)
    source_checks['no_scaler_or_scheduler_construction'] = {'verified': True, 'source_function': 'historical runner AST'}
    source_checks['frozen_encoder_and_act_head'] = {'verified': True, 'source_function': 'smoke.freeze_policy',
        'reviewed_parameter_hashes_unchanged': True}
    source_checks['allowed_trainable_groups'] = {'verified': True, 'typed_prefixes': list(historical.smoke.TYPED_PREFIXES),
        'project_groups': ['span', 'validity'], 'reviewed_names_sha256': audit.canonical_hash(names)}
    return {'fields': matrix, 'source_checks': source_checks, 'all_equal': True,
            'decoder_identity_change_only': {'historical': observed['decoder'], 'new': DECODER_VERSION},
            'recipe_sha256': audit.canonical_hash(RECIPE)}


def source_dispatch_proof(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    historical_aliases = {'historical'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            historical_aliases.update(alias.asname or alias.name for alias in node.names
                if alias.name == historical.__name__)
        if isinstance(node, ast.ImportFrom) and node.module == historical.__name__:
            audit.require(all(alias.name not in ('decode', '*') for alias in node.names), AMBIGUOUS)
    helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validation_decode']
    audit.require(len(helpers) == 1, AMBIGUOUS)
    semantic = [n for n in ast.walk(helpers[0]) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == 'decode']
    audit.require(len(semantic) == 1 and ast.unparse(semantic[0].func) == 's3_decoder.decode', AMBIGUOUS)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            audit.require(node.name not in ('decode', 'isolated', 'tighten', 'finish', 'owner', 'valid_pair'), AMBIGUOUS)
        if isinstance(node, ast.Attribute):
            audit.require(not (isinstance(node.value, ast.Name) and node.value.id in historical_aliases and node.attr == 'decode'), AMBIGUOUS)
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                audit.require(not any(ast.unparse(node).startswith(alias + '.') for alias in historical_aliases), AMBIGUOUS)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id in historical_aliases:
                audit.require(node.func.attr in ('select_subset', 'epoch_batches', 'validate_validation'), AMBIGUOUS)
        if isinstance(node, ast.While):
            raise ValueError(AMBIGUOUS)
    return {'target': 's3_decoder.decode', 'historical_decode_references': 0,
            'historical_global_mutations': 0, 'local_decoder_definitions': 0,
            'copied_seam_loops': 0, 'static_source_verified': True}


def dispatch_probe() -> dict[str, Any]:
    """Synthetic CPU call plus call profiling; no monkeypatching either imported module."""
    calls = {'s3': 0, 'historical': 0}
    # Locate historical code through source metadata, without a historical.decode reference.
    def profile(frame: Any, event: str, arg: Any) -> None:
        if event == 'call' and frame.f_code.co_name == 'decode':
            if frame.f_code.co_filename == s3_decoder.__file__:
                calls['s3'] += 1
            elif frame.f_code.co_filename == historical.__file__:
                calls['historical'] += 1
    old_profile = sys.getprofile()
    try:
        sys.setprofile(profile)
        result = validation_decode(0, 1.0, [-100, 1, -100], [False, True, False], [None, (0, 5), None], ' abc ')
    finally:
        sys.setprofile(old_profile)
    audit.require(calls == {'s3': 1, 'historical': 0}
        and result == {'intent': 'play', 'track': {'start': 1, 'end': 4}, 'artist': None, 'album': None}, AMBIGUOUS)
    return {'synthetic_calls': calls, 'masked_dispatch_and_result_verified': True, 'model_outputs_used': False}


def checkpoint_identity() -> dict[str, Any]:
    # Lexical namespace comparison only; neither historical nor future checkpoint is accessed.
    audit.require(FUTURE_CHECKPOINT_NAMESPACE != historical.CHECKPOINT_DIR
        and FUTURE_CHECKPOINT_SCHEMA != 'laya-small-adaptation-final-v1'
        and FUTURE_RESULT_SCHEMA != 'laya-small-adaptation-v1', BLOCKER + ':namespace')
    return {'namespace': str(FUTURE_CHECKPOINT_NAMESPACE), 'schema': FUTURE_CHECKPOINT_SCHEMA,
            'result_schema': FUTURE_RESULT_SCHEMA, 'distinct_from_pr79': True,
            'directory_created': False, 'checkpoint_opened': False}


def preflight() -> dict[str, Any]:
    audit.require(Path(sys.executable).resolve() == audit.PYTHON.resolve() and sys.flags.utf8_mode == 1, BLOCKER + ':python_utf8')
    audit.require(os.environ.get('HF_HUB_OFFLINE') == os.environ.get('TRANSFORMERS_OFFLINE') == '1', BLOCKER + ':offline')
    audit.require(all(os.environ.get(k, 'false').casefold() == 'false' for k in audit.FLAGS), BLOCKER + ':authority')
    opened, denied = set(), []
    guard = audit.read_guard(opened, denied)
    def no_compute_guard(event: str, args: tuple[Any, ...]) -> None:
        guard(event, args)
        if event in ('os.mkdir', 'os.rename', 'os.remove'):
            raise PermissionError(BLOCKER + ':filesystem_mutation')
    sys.addaudithook(no_compute_guard)
    repo = repo_identity()
    impl = canonical_evidence('LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json', IMPLEMENTATION_SHA)
    pr79 = canonical_evidence('LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json', PR79_SHA)
    before = historical_hashes(impl)
    identity = audit.tokenizer_identity()
    source = Path(__file__).read_text(encoding='utf-8')
    proof = {**source_dispatch_proof(source), **dispatch_probe()}
    recipe = recipe_audit(pr79)
    raw = {name: audit.split_path(name).read_bytes() for name in audit.SPLITS}
    rows = {name: audit.parse_split(name, data) for name, data in raw.items()}
    historical.validate_validation(rows['validation'])
    selected, manifest = historical.select_subset(rows['train'])
    audit.require(manifest == pr79['selection'] and manifest['manifest_sha256'] == SELECTOR_SHA, BLOCKER + ':selector')
    epochs = historical.epoch_batches(manifest['eligible_case_ids'])
    schedule_sha = [audit.canonical_hash([x for batch in epoch for x in batch]) for epoch in epochs]
    audit.require(epochs == historical.epoch_batches(manifest['eligible_case_ids'])
                  and schedule_sha == pr79['epoch_permutation_sha256'], DRIFT)
    audit.require(len(epochs) == RECIPE['epochs'] and all(len(e) == RECIPE['steps_per_epoch'] for e in epochs)
                  and sum(map(len, epochs)) == RECIPE['optimizer_steps'], DRIFT)
    audit.require(all(audit.split_path(name).read_bytes() == data for name, data in raw.items()), BLOCKER + ':data_mutated')
    after = historical_hashes(impl)
    audit.require(before == after and audit.tokenizer_identity() == identity, MUTATED)
    result = {'schema': 'laya-s3-research-preflight-v1', 'status': PASS, 'repo_base': BASE,
        'research_path': PATH_VERSION, 'decoder': DECODER_VERSION, 'repo_identity': repo,
        'research_path_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        's3_decoder_sha256': DECODER_SHA, 's3_implementation_canonical_sha256': IMPLEMENTATION_SHA,
        'historical_before': before, 'historical_after': after, 'tokenizer_identity': identity,
        'inputs': impl['inputs'], 'selector': {'algorithm': manifest['algorithm'], 'manifest_sha256': SELECTOR_SHA,
            'selected_rows': len(selected), 'selected_groups': len(manifest['source_group_ids']),
            'eligible_rows': len(manifest['eligible_case_ids']), 'blocked_rows': len(manifest['blocked_case_ids'])},
        'schedule': {'epochs': len(epochs), 'steps_per_epoch': list(map(len, epochs)),
                     'batch_sizes_per_epoch': [list(map(len, e)) for e in epochs], 'epoch_sha256': schedule_sha},
        'recipe_compatibility': recipe, 'decoder_dispatch': proof, 'future_checkpoint': checkpoint_identity(),
        'authority_flags': audit.FLAGS, 'process_boundary': {'opened_corpus_splits': sorted(opened),
            'protected_open_attempts': len(denied), 'model_weights_opened': False, 'checkpoint_opened': False,
            'checkpoint_directory_created': False, 'gpu_access': False, 'model_compute': False,
            'held_out_rows_opened': False, 'stage_a_rows_opened': False, 'app_modified': False,
            'torch_imported': 'torch' in sys.modules, 'offline': True, 'utf8_mode': sys.flags.utf8_mode}}
    result['canonical_result_sha256'] = audit.canonical_hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true', help='Run the only supported, no-compute mode.')
    parser.parse_args()
    try:
        print(json.dumps(preflight(), ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (ValueError, PermissionError) as error:
        reason = str(error)
        label = reason if reason in (AMBIGUOUS, DRIFT, MUTATED, 'STOP_REVIEWED_STATE_CHANGED') else BLOCKER
        print(json.dumps({'status': label, 'blocker': reason}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
