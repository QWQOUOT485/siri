"""Single base-model construction diagnostic with scratch-only dependency writes."""
from __future__ import annotations

import argparse
import atexit
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import traceback
from typing import Any

import local_ai_stage_b_laya_s3_pr79_validation_diagnostic as reviewed

pinned, ROOT = reviewed.pinned, reviewed.ROOT
BASE = 'fcb378031e2befff1ba7477952041647a5b8cc4a'
AUTHORIZATION = 'laya-base-load-guard-root-cause-v1'
PASS = 'LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_DIAGNOSTIC_PASSED'
BLOCKER = 'LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_DIAGNOSTIC_BLOCKER'
DATA = 'STOP_LAYA_LOAD_DIAGNOSTIC_DATA_BOUNDARY'
PROTECTED = 'STOP_LAYA_LOAD_DIAGNOSTIC_PROTECTED_WRITE'
OUTSIDE = 'STOP_LAYA_LOAD_DIAGNOSTIC_UNEXPECTED_WRITE_PATH'
NETWORK = 'STOP_LAYA_LOAD_DIAGNOSTIC_NETWORK'
CHECKPOINT = 'STOP_LAYA_LOAD_DIAGNOSTIC_CHECKPOINT_ACCESS'
SCRATCH = Path(r'D:\ai\ai\stage_b_laya_load_diagnostic\guard-regression-v1')
PRIMARY = Path(r'D:\ai\siri-spec')
RESULT = ROOT / 'docs/local_ai/stage_b/evidence/LAYA_BASE_MODEL_LOAD_ROOT_CAUSE_2026-09-27.json'
PREFIX = 'LAYA_BASE_LOAD_ROOT_CAUSE='
CACHE_BINDINGS = {'TMP': 'tmp', 'TEMP': 'tmp', 'TMPDIR': 'tmp', 'TORCHINDUCTOR_CACHE_DIR': 'torchinductor',
    'TRITON_CACHE_DIR': 'triton', 'HF_HOME': 'hf', 'HF_HUB_CACHE': 'hf/hub',
    'TRANSFORMERS_CACHE': 'hf/transformers', 'XDG_CACHE_HOME': 'xdg'}
PROTECTED_ROOTS = {'pinned_source': pinned.SOURCE, 'pinned_model': pinned.MODEL,
    'adaptation_checkpoint': reviewed.CHECKPOINT_PATH.parent, 'repository': ROOT, 'primary_worktree': PRIMARY}
FLAGS = reviewed.audit.FLAGS
canonical_hash, sha = reviewed.canonical_hash, reviewed.sha


def require(ok: bool, detail: str) -> None:
    if not ok:
        raise ValueError(detail)


def under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def category(value: Any, scratch: Path = SCRATCH) -> dict[str, str]:
    if not isinstance(value, (str, bytes, os.PathLike)):
        return {'path_category': 'outside_scratch', 'basename': '<file-descriptor>', 'suffix': ''}
    path = Path(os.fsdecode(value)).absolute()
    resolved = path.resolve()
    for name, root in PROTECTED_ROOTS.items():
        if under(path, root) or under(resolved, root.resolve()):
            return {'path_category': name, 'basename': path.name, 'suffix': path.suffix}
    if under(path, scratch) and under(resolved, scratch.resolve()):
        return {'path_category': 'diagnostic_scratch', 'relative_path': path.relative_to(scratch).as_posix()}
    return {'path_category': 'outside_scratch', 'basename': path.name, 'suffix': path.suffix}


def sanitized_message(message: str) -> str:
    # Replace roots first, then any remaining Windows/UNC absolute path fragments.
    for name, path in sorted({**PROTECTED_ROOTS, 'diagnostic_scratch': SCRATCH,
        'qualified_runtime': pinned.PYTHON.parent.parent, 'python_runtime': Path(sys.base_prefix),
        'user_home': Path.home()}.items(), key=lambda item: len(str(item[1])), reverse=True):
        message = re.sub(re.escape(str(path)), '<' + name + '>', message, flags=re.I)
        message = re.sub(re.escape(path.as_posix()), '<' + name + '>', message, flags=re.I)
    return re.sub(r'(?i)(?:[a-z]:[\\/]|\\\\)[^\r\n\x27\x22<>]+', '<outside_scratch>', message)[:2000]


def exception_record(exc: BaseException, stage: str) -> dict[str, Any]:
    def filename(name: str):
        value = getattr(exc, name, None)
        if value is None:
            return None
        record = category(value)
        return {'path_category': record['path_category'], 'basename': Path(os.fsdecode(value)).name}
    return {'class': type(exc).__name__, 'message': sanitized_message(str(exc)),
        'errno': getattr(exc, 'errno', None), 'winerror': getattr(exc, 'winerror', None),
        'filename': filename('filename'), 'filename2': filename('filename2'), 'stage': stage,
        'frames': [{'module_basename': Path(frame.filename).name, 'function': frame.name, 'line': frame.lineno}
            for frame in traceback.extract_tb(exc.__traceback__)]}


class Audit:
    """One process-local policy with a sticky first denial, including swallowed dependency errors."""
    def __init__(self, scratch: Path = SCRATCH):
        self.scratch, self.stage = scratch, 'identity'
        self.counts = Counter(total_filesystem_events=0, allowed_scratch_events=0,
            denied_protected_events=0, denied_outside_events=0, network_attempts=0,
            dataset_open_attempts=0, checkpoint_open_attempts=0, allowed_scratch_open_writes=0)
        self.by_event, self.details, self.first_denial = Counter(), [], None

    def deny(self, label: str, event: str, info: dict[str, Any]) -> None:
        if self.first_denial is None:
            self.first_denial = {'label': label, 'event': event, 'stage': self.stage, **info}
        raise PermissionError(label)

    def check(self) -> None:
        if self.first_denial:
            raise PermissionError(self.first_denial['label'])

    def __call__(self, event: str, args: tuple[Any, ...]) -> None:
        if event in ('socket.connect', 'socket.getaddrinfo'):
            self.counts['network_attempts'] += 1
            self.deny(NETWORK, event, {})
        paths = []
        if event == 'open':
            path, mode, flags = args[:3]
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int)
                and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if not writing and isinstance(path, (str, bytes, os.PathLike)):
                lexical = Path(os.fsdecode(path)).absolute()
                resolved = Path(os.fsdecode(path)).resolve()
                if (lexical.name.casefold() in ('train.jsonl', 'validation.jsonl', 'held_out.jsonl', 'ai_intent_cases.json')
                    or any(under(p, root / sub) for p in (lexical, resolved) for root in (ROOT, PRIMARY) for sub in ('artifacts', 'tests/fixtures'))):
                    self.counts['dataset_open_attempts'] += 1
                    self.deny(DATA, event, category(path, self.scratch))
                if any(under(p, reviewed.CHECKPOINT_PATH.parent) for p in (lexical, resolved)) or lexical.suffix.casefold() in ('.pt', '.pth', '.ckpt'):
                    self.counts['checkpoint_open_attempts'] += 1
                    self.deny(CHECKPOINT, event, category(path, self.scratch))
            if writing:
                paths = [path]
        elif event in ('os.mkdir', 'os.chmod', 'os.remove', 'os.rmdir', 'os.truncate', 'os.utime'):
            paths = [args[0]]
        elif event in ('os.rename', 'os.link', 'os.symlink'):
            paths = list(args[:2])
        if not paths:
            return
        self.counts['total_filesystem_events'] += 1
        self.by_event[event] += 1
        infos = [category(path, self.scratch) for path in paths]
        for info in infos:
            if len(self.details) < 200:
                self.details.append({'event': event, 'stage': self.stage, **info})
        if any(info['path_category'] in PROTECTED_ROOTS for info in infos):
            self.counts['denied_protected_events'] += 1
            self.deny(PROTECTED, event, next(info for info in infos if info['path_category'] in PROTECTED_ROOTS))
        if any(info['path_category'] != 'diagnostic_scratch' for info in infos):
            self.counts['denied_outside_events'] += 1
            self.deny(OUTSIDE, event, next(info for info in infos if info['path_category'] != 'diagnostic_scratch'))
        self.counts['allowed_scratch_events'] += 1
        if event == 'open':
            self.counts['allowed_scratch_open_writes'] += 1

    def summary(self) -> dict[str, Any]:
        return {'counts': dict(self.counts), 'counts_by_event': dict(self.by_event),
            'details': self.details, 'detail_cap': 200, 'first_denial': self.first_denial}


def protected_identity() -> dict[str, Any]:
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve() and sys.version_info[:3] == (3, 14, 7), 'qualified_python')
    require(sys.flags.utf8_mode == 1 and sys.dont_write_bytecode, 'process_flags')
    reviewed.authority_check()
    require(os.environ.get('HF_HUB_OFFLINE') == os.environ.get('TRANSFORMERS_OFFLINE') == '1'
        and not os.environ.get('PYTHONPATH'), 'offline_environment')
    require(reviewed.git('rev-parse', 'origin/main') == reviewed.git('merge-base', 'HEAD', BASE) == BASE, 'STOP_REVIEWED_STATE_CHANGED')
    versions = {name: importlib.metadata.version(name) for name in pinned.EXPECTED_PACKAGES}
    require(versions == pinned.EXPECTED_PACKAGES and importlib.metadata.version('torch') == '2.13.0+rocm10.0.0', 'package_versions')
    inventory = pinned.package_inventory()
    require(inventory == '3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337', 'venv_inventory')
    sources = {}
    for path in sorted((ROOT / 'scripts').glob('local_ai_stage_b_laya*.py')):
        if path.resolve() == Path(__file__).resolve():
            continue
        relative = path.relative_to(ROOT).as_posix()
        # Git tracks LF while checkout may use CRLF: compare repository blob with clean-filter output.
        require(reviewed.git('hash-object', str(path)) == reviewed.git('rev-parse', BASE + ':' + relative), 'historical_source_drift')
        sources[path.name] = sha(path)
    require(sources['local_ai_stage_b_laya_s3_pr79_validation_diagnostic.py'] == '4b259bd9629628aeb3d25ad231521a745cfec81ac0ea6ce6786386259ef94b4f', 'pr86_runner_identity')
    reviewed.source_identity()
    evidence = {}
    for name, expected in (('LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json', reviewed.research.PR79_SHA),
        ('LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json', 'ae78d9fec05a9e7200856fb723f417b46877114783b3e6c4627599bd8f9b5dbd')):
        reviewed.research.canonical_evidence(name, expected)
        evidence[name] = sha(ROOT / 'docs/local_ai/stage_b/evidence' / name)
    for name in ('LOCAL_AI_STAGE_B_LAYA_SMALL_ADAPTATION_2026-09-26.md', 'LOCAL_AI_STAGE_B_LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.md'):
        evidence[name] = sha(ROOT / 'docs/local_ai/stage_b/evidence' / name)
    files, aggregate = pinned.artifact_inventory()
    pinned.model_identity(files, aggregate)
    tokenizer = reviewed.audit.tokenizer_identity()
    config = json.loads((pinned.MODEL / 'tokenizer/tokenizer_config.json').read_bytes())
    require(config.get('tokenizer_class') not in (None, 'TokenizersBackend')
        and not isinstance(config.get('extra_special_tokens'), list), 'tokenizer_config_fix_not_noop')
    return {'source_revision': pinned.source_identity(), 'source_clean': True, 'model_aggregate': aggregate,
        'model_files': files, 'tokenizer': tokenizer, 'tokenizer_fix_is_noop': True, 'venv_inventory': inventory,
        'package_versions': versions, 'historical_sources': sources, 'accepted_evidence': evidence}


def scratch_safe(require_absent: bool = False) -> None:
    require(SCRATCH.is_absolute() and SCRATCH.name == 'guard-regression-v1', 'scratch_identity')
    for root in PROTECTED_ROOTS.values():
        require(not under(SCRATCH, root) and not under(root, SCRATCH), 'scratch_protected_overlap')
    for path in (SCRATCH, *SCRATCH.parents):
        if path.exists():
            require(not path.is_symlink() and not path.is_junction()
                and not path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT, 'scratch_redirected')
    if require_absent:
        require(not SCRATCH.exists(), 'scratch_preexists')


def preflight() -> dict[str, Any]:
    guard = Audit()
    sys.addaudithook(guard)
    identity = protected_identity()
    guard.check()
    scratch_safe(require_absent=True)
    require(not RESULT.exists(), 'durable_result_preexists')
    return {'status': 'LAYA_BASE_LOAD_DIAGNOSTIC_PREFLIGHT_PASSED_NO_COMPUTE', 'repo_base': BASE,
        'runner_sha256': sha(Path(__file__)), 'identity': identity, 'authority_flags': dict(FLAGS),
        'checkpoint_opened': False, 'dataset_opened': False, 'cache_bindings': CACHE_BINDINGS,
        'scratch_category': 'diagnostic_scratch', 'audit': guard.summary(), 'model_load_attempts': 0}


def vram(torch: Any, target: Any) -> dict[str, int]:
    return {'allocated': torch.cuda.memory_allocated(target), 'reserved': torch.cuda.memory_reserved(target),
        'peak_allocated': torch.cuda.max_memory_allocated(target), 'peak_reserved': torch.cuda.max_memory_reserved(target)}


def one_load(laya: Any, counts: dict[str, int]):
    require(counts['laya_load_attempts'] == 0, 'extra_load_forbidden')
    counts['laya_load_attempts'] += 1
    agent = laya.load(str(pinned.MODEL), device='cuda:1')
    counts['laya_load_completed'] += 1
    return agent


def inventory_scratch() -> list[dict[str, Any]]:
    scratch_safe()
    rows = []
    for path in sorted(SCRATCH.rglob('*')):
        require(not path.is_symlink() and not path.is_junction(), 'scratch_inventory_redirected')
        if path.is_file():
            rows.append({'relative_path': path.relative_to(SCRATCH).as_posix(),
                'size_bytes': path.stat().st_size, 'sha256': sha(path)})
    return rows


def child() -> tuple[dict[str, Any], Audit]:
    guard = Audit()
    sys.addaudithook(guard)
    counts = dict(live_invocations=1, laya_load_attempts=0, laya_load_completed=0,
        checkpoint_loads=0, dataset_passes=0, forward_calls=0, training_steps=0, backward_calls=0)
    result = {'schema': 'laya-base-load-root-cause-v1', 'status': BLOCKER, 'repo_base': BASE,
        'task_scoped_authorization': AUTHORIZATION, 'authority_flags': dict(FLAGS), 'execution_counts': counts,
        'runner_sha256': sha(Path(__file__)), 'scratch_namespace': 'diagnostic_scratch',
        'cache_bindings': CACHE_BINDINGS, 'scratch_created': True, 'checkpoint_opened': False,
        'dataset_opened': False, 'optimizer_constructed': False, 'scheduler_constructed': False,
        'pr86_global_write_guard_regression_supported': False, 'vram': {}}
    before = None
    try:
        require(os.environ.get('LAYA_LOAD_DIAGNOSTIC_TASK') == AUTHORIZATION, 'task_authorization')
        require(os.environ.get('GIT_OPTIONAL_LOCKS') == '0', 'git_optional_locks')
        require(os.environ.get('LAYA_LOAD_DIAGNOSTIC_SOURCE_SHA') == result['runner_sha256'], 'frozen_source')
        require(not reviewed.git('status', '--porcelain'), 'dirty_pre_live_commit')
        result['pre_live_commit'] = reviewed.git('rev-parse', 'HEAD')
        require(not RESULT.exists(), 'durable_result_preexists')
        scratch_safe()
        require(SCRATCH.is_dir() and all(os.environ.get(key) == str(SCRATCH / value) for key, value in CACHE_BINDINGS.items()), 'scratch_environment')
        before = protected_identity()
        result['identities_before'] = before
        guard.stage = 'dependency_import'
        import torch
        require(torch.__version__ == '2.13.0+rocm10.0.0' and torch.version.hip == '7.15.26333'
            and torch.version.cuda is None, 'torch_build')
        devices = [vars(d) for d in pinned.enumerate_accelerators(torch)]
        device = reviewed.select_device(devices)
        result.update(visible_devices=devices, selected_device=device)
        target = torch.device(device)
        torch.cuda.set_device(target)
        require(torch.cuda.current_device() == 1, 'current_device')
        torch.cuda.reset_peak_memory_stats(target)
        result['vram']['baseline'] = vram(torch, target)
        sys.path.insert(0, str(pinned.SOURCE))
        import laya
        require(Path(laya.__file__).resolve() == pinned.SOURCE / 'laya/__init__.py', 'pinned_laya_import')
        guard.check()
        guard.stage = 'laya_load'
        started = time.perf_counter()
        agent = one_load(laya, counts)
        guard.check()
        torch.cuda.synchronize(target)
        result['load_seconds'] = time.perf_counter() - started
        guard.stage = 'residency_readback'
        result['residency'] = pinned.residency(agent, 'cuda:1')
        require(result['residency']['cpu_fallback'] is False, 'cpu_fallback')
        result['vram']['after_load'] = vram(torch, target)
        result['vram']['peak'] = result['vram']['after_load']
        del agent
        guard.check()
        result['status'] = PASS
    except Exception as exc:
        result['exception'] = exception_record(exc, guard.stage)
        result['status'] = guard.first_denial['label'] if guard.first_denial else BLOCKER
    finally:
        guard.stage = 'post_identity'
        if before is not None:
            try:
                after = protected_identity()
                result['identities_after'] = after
                require(before == after, 'protected_identity_changed')
            except Exception as exc:
                result.update(status=BLOCKER, post_identity_exception=exception_record(exc, guard.stage))
        guard.stage = 'dependency_exit'
    return result, guard


def finish_child(result: dict[str, Any], guard: Audit) -> None:
    """Registered before imports, so dependency atexit mutations are also in the audit."""
    result['audit'] = guard.summary()
    if guard.first_denial:
        result['status'] = guard.first_denial['label']
    # Parent decides support only after inventory proves nonempty dependency files exist.
    result['pr86_global_write_guard_regression_supported'] = False
    result['canonical_result_sha256'] = canonical_hash(result)
    print(PREFIX + json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))


def supports_guard_hypothesis(result: dict[str, Any]) -> bool:
    return (result['status'] == PASS and result.get('identities_before') == result.get('identities_after')
        and result['audit']['counts']['allowed_scratch_open_writes'] > 0
        and any(row['size_bytes'] > 0 for row in result['scratch_inventory']))


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    # No audit hook in parent: it creates/inventories/removes only this predeclared namespace.
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve() and sys.flags.utf8_mode == 1, 'parent_runtime')
    scratch_safe(require_absent=True)
    require(not RESULT.exists(), 'durable_result_preexists')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update({key: str(SCRATCH / value) for key, value in CACHE_BINDINGS.items()})
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', GIT_OPTIONAL_LOCKS='0',
        LAYA_LOAD_DIAGNOSTIC_TASK=AUTHORIZATION, LAYA_LOAD_DIAGNOSTIC_SOURCE_SHA=sha(Path(__file__)))
    result = {'schema': 'laya-base-load-root-cause-v1', 'status': BLOCKER, 'repo_base': BASE,
        'task_scoped_authorization': AUTHORIZATION, 'authority_flags': dict(FLAGS),
        'runner_sha256': sha(Path(__file__)), 'scratch_namespace': 'diagnostic_scratch',
        'cache_bindings': CACHE_BINDINGS, 'scratch_created': False,
        'execution_counts': {'live_invocations': 0}, 'pr86_global_write_guard_regression_supported': False}
    try:
        SCRATCH.mkdir(parents=True, exist_ok=False)
        result['scratch_created'] = True
        for relative in sorted(set(CACHE_BINDINGS.values())):
            (SCRATCH / relative).mkdir(parents=True, exist_ok=True)
        result['execution_counts'] = dict.fromkeys(('laya_load_attempts', 'laya_load_completed',
            'checkpoint_loads', 'dataset_passes', 'forward_calls', 'training_steps', 'backward_calls'), None)
        result['execution_counts']['live_invocations'] = 1
        completed = runner([str(pinned.PYTHON), '-B', '-X', 'utf8', str(Path(__file__).resolve()), '--child'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False, env=env, timeout=300)
        matches = [line[len(PREFIX):] for line in completed.stdout.decode('utf-8', 'strict').splitlines() if line.startswith(PREFIX)]
        require(len(matches) == 1, 'child_result_missing_or_ambiguous')
        parsed = json.loads(matches[0])
        require(parsed.pop('canonical_result_sha256') == canonical_hash(parsed), 'child_hash')
        result = parsed
        result['child_returncode'] = completed.returncode
        require(completed.returncode == 0, 'child_exit')
    except Exception as exc:
        result.update(status=BLOCKER, transport_exception=exception_record(exc, 'parent_transport'))
    finally:
        if result['scratch_created']:
            try:
                result['scratch_inventory'] = inventory_scratch()
                result['pr86_global_write_guard_regression_supported'] = supports_guard_hypothesis(result)
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
    options.add_argument('--load-diagnostic', action='store_true')
    options.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        holder = []
        atexit.register(lambda: finish_child(*holder) if holder else None)
        holder.extend(child())
        return 0
    result = parent() if args.load_diagnostic else preflight()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False))
    return 0 if result['status'] in (PASS, 'LAYA_BASE_LOAD_DIAGNOSTIC_PREFLIGHT_PASSED_NO_COMPUTE') else 1


if __name__ == '__main__':
    raise SystemExit(main())
