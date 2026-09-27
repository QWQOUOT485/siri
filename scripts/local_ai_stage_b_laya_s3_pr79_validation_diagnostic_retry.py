"""One PR79 validation pass, shared historical/S3 decisions, reviewed scratch-only writes."""
from __future__ import annotations

import argparse
import atexit
import importlib.metadata
import json
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

pinned, historical, smoke, ROOT = prior.pinned, prior.historical, prior.smoke, prior.ROOT
BASE = '144dc020344936c017f13ccf9253902d5af54c44'
AUTHORIZATION = 'pr79-checkpoint-s3-validation-diagnostic-retry-v1'
PASS, BLOCKER = prior.PASS, 'LAYA_PR79_S3_DIAGNOSTIC_RETRY_NEW_BLOCKER'
SCRATCH = Path(r'D:\ai\ai\stage_b_laya_validation_diagnostic\s3-pr79-v1')
RESULT = ROOT / 'docs/local_ai/stage_b/evidence/LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_RETRY_2026-09-27.json'
PREFIX = 'LAYA_S3_PR79_VALIDATION_RETRY='
PREFLIGHT = 'LAYA_S3_PR79_RETRY_PREFLIGHT_PASSED_NO_COMPUTE'
CACHE_BINDINGS = load_guard.CACHE_BINDINGS
canonical_hash, sha, require = prior.canonical_hash, prior.sha, prior.require
EVIDENCE = {
 'LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json': prior.research.PR79_SHA,
 'LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json': prior.research.IMPLEMENTATION_SHA,
 'LAYA_S3_RESEARCH_PATH_PREFLIGHT_2026-09-27.json': '38bdead38e5dea83cf45e522279e7280fdfa0aeb08d8d6e12984cff1d7591d87',
 'LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json': 'ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd',
 'LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_2026-09-27.json': '962b0f0b720fd87cb21b7a22cadc228150733327e2dfcc318628de28194f5535'}


class Audit(load_guard.Audit):
    """Only add exact read-only validation/checkpoint exceptions to the reviewed write policy."""
    def __init__(self):
        super().__init__(SCRATCH)
        self.allowed_reads = {'validation': 0, 'pr79_checkpoint': 0}

    def deny(self, label: str, event: str, info: dict[str, Any]) -> None:
        super().deny({load_guard.DATA: prior.DATA, load_guard.CHECKPOINT: prior.CHECKPOINT}.get(label, label), event, info)

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            path, mode, flags = args[:3]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int)
                and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if not writing:
                lexical = Path(os.fsdecode(path)).absolute()
                for name, allowed in (('validation', prior.VALIDATION), ('pr79_checkpoint', prior.CHECKPOINT_PATH)):
                    if lexical == allowed and lexical.resolve() == allowed:
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
    if record['status'] == prior.BLOCKER:
        record['status'] = BLOCKER
    return record


def identities() -> tuple[dict[str, Any], list[Any], dict[str, Any]]:
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
        and sources['local_ai_stage_b_laya_base_load_root_cause.py'] == '5e82645ec396509155fcb85d9d24989729be84ce81b08e550e32e5a3098f163e', prior.SOURCE)
    evidence = {}
    for name, digest in EVIDENCE.items():
        prior.research.canonical_evidence(name, digest)
        evidence[name] = {'canonical_sha256': digest, 'byte_sha256': sha(ROOT / 'docs/local_ai/stage_b/evidence' / name)}
    reports = {path.name: sha(path) for path in (ROOT / 'docs/local_ai/stage_b/evidence').glob('LOCAL_AI_STAGE_B_LAYA*.md')
        if 'DIAGNOSTIC_RETRY' not in path.name}
    accepted = prior.accepted_evidence()
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
        'validation_sha256': sha(prior.VALIDATION), 'validation_composition': composition}, rows, accepted


def scratch_safe(absent: bool = False) -> None:
    require(SCRATCH.is_absolute() and SCRATCH.name == 's3-pr79-v1', BLOCKER, 'scratch_identity')
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
    identity, _, _ = identities()
    guard.check()
    scratch_safe(absent=True)
    require(not RESULT.exists(), BLOCKER, 'durable_result_preexists')
    return {'status': PREFLIGHT, 'repo_base': BASE, 'runner_sha256': sha(Path(__file__)), 'identities': identity,
        'authority_flags': dict(prior.audit.FLAGS), 'audit': guard.summary(), 'allowed_reads': guard.allowed_reads,
        'model_loads': 0, 'checkpoint_deserializations': 0, 'validation_passes': 0}


def validation_pass(result: dict[str, Any], rows: list[Any], items: list[Any], infer: Any, guard: Audit):
    """Fixed coverage once; infer returns one set of raw shared decisions per batch."""
    counts = result['execution_counts']
    require(counts['validation_passes'] == 0 and len(rows) == len(items) == 540
        and len({r.case_id for r in rows}) == 540 and all(r.ai_scope == 'supported' for r in rows), prior.DATA, 'validation_coverage')
    counts['validation_passes'] += 1
    old, new, decisions, batches = [], [], [], []
    for start in range(0, 540, 16):
        guard.check()
        batch_rows, batch_items = rows[start:start + 16], items[start:start + 16]
        counts['validation_forward_batches'] += 1
        typed, probabilities, validities, labels = infer(batch_items)
        guard.check()
        a, b, c = prior.dual_decode(batch_rows, batch_items, typed, probabilities, validities, labels)
        old.extend(a); new.extend(b); decisions.extend(c)
        for key in ('shared_model_decisions', 'historical_decoder_calls', 's3_decoder_calls'):
            counts[key] += len(batch_rows)
        batches.append([r.case_id for r in batch_rows])
    require([len(b) for b in batches] == [16] * 33 + [12], prior.DATA, 'batches')
    result['batch_case_ids'] = batches
    return old, new, decisions


def child() -> tuple[dict[str, Any], Audit]:
    guard = Audit()
    sys.addaudithook(guard)
    counts = dict(live_invocations=1, model_load_attempts=0, model_loads=0, checkpoint_load_attempts=0,
        checkpoint_loads=0, validation_passes=0, validation_forward_batches=0, shared_model_decisions=0,
        historical_decoder_calls=0, s3_decoder_calls=0, additional_model_forwards_for_second_decoder=0,
        training_steps=0, backward_calls=0, optimizer_constructed=False, scheduler_constructed=False)
    result = {'schema': 'laya-s3-pr79-validation-diagnostic-retry-v1', 'status': BLOCKER,
        'NON_ACCEPTANCE_DIAGNOSTIC_ONLY': True, 'repo_base': BASE, 'task_scoped_compute_authorization': AUTHORIZATION,
        'authority_flags': dict(prior.audit.FLAGS), 'persistent_training_authorized': False,
        'persistent_model_compute_authorized': False, 'runner_sha256': sha(Path(__file__)),
        'scratch_created': True, 'scratch_namespace': 'diagnostic_scratch', 'cache_bindings': CACHE_BINDINGS,
        'execution_counts': counts, 'vram': {}, 'runtime_seconds': {}}
    before, hook = None, None
    try:
        require(os.environ.get('LAYA_VALIDATION_RETRY_TASK') == AUTHORIZATION
            and os.environ.get('LAYA_VALIDATION_RETRY_SHA') == result['runner_sha256'], BLOCKER, 'task_source_binding')
        require(os.environ.get('GIT_OPTIONAL_LOCKS') == '0', BLOCKER, 'git_optional_locks')
        require(not prior.git('status', '--porcelain'), BLOCKER, 'dirty_pre_live_commit')
        result['pre_live_commit'] = prior.git('rev-parse', 'HEAD')
        require(not RESULT.exists(), BLOCKER, 'durable_result_preexists')
        scratch_safe()
        require(SCRATCH.is_dir() and all(os.environ.get(key) == str(SCRATCH / value) for key, value in CACHE_BINDINGS.items()), BLOCKER, 'scratch_environment')
        before, all_rows, accepted = identities()
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
        old, new, decisions = validation_pass(result, rows, items, infer, guard)
        guard.check()
        torch.cuda.synchronize(target)
        result['runtime_seconds']['validation_wall'] = time.perf_counter() - started
        result['vram']['validation_peak'] = smoke.vram(torch, target)
        result['parameter_hashes_after'] = smoke.group_hashes(model, span, validity)
        require(result['parameter_hashes_after'] == prior.PARAMETERS, prior.RESTORE, 'after_validation')
        result['vram']['final'] = smoke.vram(torch, target)
        result['historical'] = prior.report(rows, old, decisions)
        result['historical_reproduction'] = prior.reproduction(result['historical'], accepted['validation'])
        result['s3'] = prior.report(rows, new, decisions)
        require(prior.safety(result['s3']), prior.SAFETY)
        result['safety_gate_passed'] = True
        result['shared_decisions'] = decisions
        result['analysis'] = prior.analysis(rows, old, new, decisions)
        for slot, denominator in (('track', 300), ('artist', 126), ('album', 204)):
            result['analysis']['slots'][slot]['null_on_gold_play'] = 300 - result['analysis']['slots'][slot]['presence']
            result['analysis']['structural_oracle_gap'][slot]['gold_present_denominator'] = denominator
        for entry in result['analysis']['historical_eleven_plays']:
            entry['s3_track_exact'] = entry['s3']['track'] == entry['gold']['track']
        result['status'] = PASS
    except Exception as exc:
        result.update(failure_record(exc), exception=exception_record(exc, guard.stage))
    finally:
        if hook is not None:
            hook.remove()
        guard.stage = 'post_identity'
        if before is not None:
            try:
                after, _, _ = identities()
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
        LAYA_VALIDATION_RETRY_TASK=AUTHORIZATION, LAYA_VALIDATION_RETRY_SHA=sha(Path(__file__)))
    result = {'schema': 'laya-s3-pr79-validation-diagnostic-retry-v1', 'status': BLOCKER, 'repo_base': BASE,
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
