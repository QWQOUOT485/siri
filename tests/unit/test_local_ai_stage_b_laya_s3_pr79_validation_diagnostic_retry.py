"""CPU/synthetic retry boundaries; tests never dispatch live mode."""
import ast
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as N

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import local_ai_stage_b_laya_s3_pr79_validation_diagnostic_retry as d


@pytest.mark.parametrize('path,name', [(d.prior.VALIDATION, 'validation'), (d.prior.CHECKPOINT_PATH, 'pr79_checkpoint')])
def test_only_exact_read_exceptions(path, name):
    guard = d.Audit()
    guard('open', (str(path), 'rb', os.O_RDONLY))
    guard.check()
    assert guard.allowed_reads[name] == 1 and not guard.details
    with pytest.raises(PermissionError, match=d.load_guard.PROTECTED):
        guard('open', (str(path), 'rb+', os.O_RDWR))
    with pytest.raises(PermissionError):
        guard.check()


@pytest.mark.parametrize('path', [d.prior.VALIDATION, d.prior.CHECKPOINT_PATH])
def test_exact_read_rejects_resolved_alias(monkeypatch, path):
    original = Path.resolve
    monkeypatch.setattr(Path, 'resolve', lambda self, *a, **kw: path.parent / 'redirected' if self == path else original(self, *a, **kw))
    with pytest.raises(PermissionError):
        d.Audit()('open', (str(path), 'rb', os.O_RDONLY))


@pytest.mark.parametrize('path', [d.prior.VALIDATION.parent / 'train.jsonl', d.prior.VALIDATION.parent / 'held_out.jsonl',
    d.ROOT / 'tests/fixtures/ai_intent_cases.json', d.SCRATCH / 'validation.jsonl', d.SCRATCH / 'other.pt'])
def test_other_dataset_checkpoint_reads_denied(path):
    with pytest.raises(PermissionError):
        d.Audit()('open', (str(path), 'rb', os.O_RDONLY))


@pytest.mark.parametrize('event', ['open', 'os.mkdir', 'os.chmod', 'os.remove', 'os.rmdir', 'os.truncate', 'os.utime', 'os.rename', 'os.link', 'os.symlink'])
def test_new_scratch_only_write_policy(event):
    guard = d.Audit()
    args = (str(d.SCRATCH / 'tmp/a'), 'wb', os.O_WRONLY) if event == 'open' else (str(d.SCRATCH / 'tmp/a'), str(d.SCRATCH / 'tmp/b'))
    guard(event, args)
    assert guard.counts['allowed_scratch_events'] == 1
    outside = (str(d.load_guard.SCRATCH / 'a'), 'wb', os.O_WRONLY) if event == 'open' else (str(d.load_guard.SCRATCH / 'a'), str(d.SCRATCH / 'tmp/b'))
    with pytest.raises(PermissionError, match=d.load_guard.OUTSIDE):
        guard(event, outside)


@pytest.mark.parametrize('event', ['os.rename', 'os.link', 'os.symlink'])
def test_protected_destination_rejected(event):
    with pytest.raises(PermissionError, match=d.load_guard.PROTECTED):
        d.Audit()(event, (str(d.SCRATCH / 'a'), str(d.pinned.MODEL / 'b')))


def test_network_and_swallowed_denial_remain_latched():
    guard = d.Audit()
    with pytest.raises(PermissionError, match=d.load_guard.NETWORK):
        guard('socket.connect', ())
    first = dict(guard.first_denial)
    with pytest.raises(PermissionError):
        guard('os.mkdir', (str(d.ROOT),))
    assert guard.first_denial == first
    with pytest.raises(PermissionError, match=d.load_guard.NETWORK):
        guard.check()


def synthetic():
    rows = [N(case_id=f'synthetic-{i}', ai_scope='supported', utterance=' abc') for i in range(540)]
    items = [{'user_state_mask': [False, True, True, False], 'token_offsets': [None, (0, 2), (2, 4), None]} for _ in rows]
    result = {'execution_counts': dict.fromkeys(('validation_passes', 'validation_forward_batches', 'shared_model_decisions', 'historical_decoder_calls', 's3_decoder_calls'), 0)}
    return rows, items, result


def test_one_pass_actual_dual_dispatch_shared_decisions_mask_and_outputs(monkeypatch):
    rows, items, result = synthetic()
    seen_old, seen_new, forwards = [], [], []
    old, new = object(), object()
    monkeypatch.setattr(d.prior.historical, 'decode', lambda *args: seen_old.append(args) or old)
    monkeypatch.setattr(d.prior.research.s3_decoder, 'decode', lambda *args: seen_new.append(args) or new)
    def infer(batch):
        forwards.append(batch)
        return [0] * len(batch), [.8] * len(batch), [.9] * len(batch), [[99, 1, 2, 99, 7]] * len(batch)
    a, b, decisions = d.validation_pass(result, rows, items, infer, d.Audit())
    assert a == [old] * 540 and b == [new] * 540 and len(decisions) == 540
    assert [len(x) for x in forwards] == [16] * 33 + [12]
    assert result['execution_counts'] == dict(validation_passes=1, validation_forward_batches=34,
        shared_model_decisions=540, historical_decoder_calls=540, s3_decoder_calls=540)
    assert sum(result['batch_case_ids'], []) == [r.case_id for r in rows]
    for left, right, item in zip(seen_old, seen_new, items):
        assert left == right == (0, .9, [0, 1, 2, 0], item['user_state_mask'], item['token_offsets'], ' abc')
        assert left[3] is right[3] and left[4] is right[4]
    with pytest.raises(ValueError, match=d.prior.DATA):
        d.validation_pass(result, rows, items, infer, d.Audit())
    assert len(forwards) == 34


@pytest.mark.parametrize('mutation', ['blocked', 'short', 'duplicate'])
def test_coverage_fails_before_forward(mutation):
    rows, items, result = synthetic()
    if mutation == 'blocked': rows[0].ai_scope = 'safety_only'
    elif mutation == 'short': rows.pop()
    else: rows[0].case_id = rows[1].case_id
    with pytest.raises(ValueError, match=d.prior.DATA):
        d.validation_pass(result, rows, items, lambda _: pytest.fail('forward reached'), d.Audit())


def test_swallowed_denial_during_forward_stops_before_decode(monkeypatch):
    rows, items, result = synthetic()
    guard = d.Audit()
    monkeypatch.setattr(d.prior, 'dual_decode', lambda *a: pytest.fail('decode reached'))
    def infer(batch):
        try: guard('socket.connect', ())
        except PermissionError: pass
        return [], [], [], []
    with pytest.raises(PermissionError):
        d.validation_pass(result, rows, items, infer, guard)
    assert result['execution_counts']['validation_forward_batches'] == 1


def test_source_single_calls_and_no_training_or_old_entrypoints():
    source = Path(d.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert calls.count('laya.load') == calls.count('torch.load') == calls.count('historical.forward') == 1
    assert not any(s.endswith(('.backward', '.step')) or '.optim.' in s for s in calls)
    assert not set(calls) & {'torch.save', 'prior.child', 'prior.parent', 'prior.preflight', 'prior.no_compute_identity',
        'load_guard.protected_identity', 'load_guard.parent', 'load_guard.child', 'load_guard.scratch_safe'}
    assert "map_location='cpu', weights_only=True" in source and 'with torch.no_grad()' in source
    assert 'module.eval()' in source and 'module.requires_grad_(False)' in source
    assert source.index("result['historical_reproduction']") < source.index("result['s3'] =")
    assert source.index('guard.check()', source.index("guard.stage = 'checkpoint_restore'")) < source.index('payload = torch.load')
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assert not any(ast.unparse(t).startswith(('prior.', 'historical.', 'load_guard.')) for t in targets)


def test_reviewed_binding_and_flag_checks_present():
    source = inspect.getsource(d.identities)
    assert 'prior.authority_check()' in source and 'canonical_evidence(name, digest)' in source
    assert len(d.EVIDENCE) == 5
    assert d.EVIDENCE['LAYA_S3_PR79_VALIDATION_DIAGNOSTIC_2026-09-27.json'].startswith('ae78d9')
    assert 'parse_validation' in source and 'parse_train' not in source


@pytest.mark.parametrize('failure', ['timeout', 'missing', 'abnormal', 'success'])
def test_raw_parent_transport_cleanup_once(monkeypatch, tmp_path, failure):
    scratch = tmp_path / 's3-pr79-v1'
    monkeypatch.setattr(d, 'SCRATCH', scratch)
    monkeypatch.setattr(d, 'RESULT', tmp_path / 'absent.json')
    calls = []
    def runner(argv, **kw):
        calls.append((argv, kw))
        assert argv[1:4] == ['-B', '-X', 'utf8'] and argv[-1] == '--child'
        assert kw['text'] is False and 'PYTHONPATH' not in kw['env']
        assert kw['env']['GIT_OPTIONAL_LOCKS'] == '0'
        assert all(kw['env'][key] == str(scratch / value) for key, value in d.CACHE_BINDINGS.items())
        if failure == 'timeout': raise subprocess.TimeoutExpired(argv, 600)
        value = {'status': d.PASS, 'scratch_created': True, 'execution_counts': {'live_invocations': 1}}
        value['canonical_result_sha256'] = d.canonical_hash(value)
        raw = (d.PREFIX + json.dumps(value)).encode() if failure != 'missing' else b'no result'
        return N(returncode=1 if failure == 'abnormal' else 0, stdout=raw, stderr=b'')
    value = d.parent(runner)
    assert len(calls) == 1 and value['execution_counts']['live_invocations'] == 1
    assert value['scratch_cleaned'] and not scratch.exists()
    assert value['status'] == (d.PASS if failure == 'success' else d.BLOCKER)
    digest = value.pop('canonical_result_sha256')
    assert digest == d.canonical_hash(value)
    if failure in ('timeout', 'missing'): assert value['execution_counts']['model_loads'] is None


def test_preexisting_scratch_rejected_without_dispatch(monkeypatch, tmp_path):
    scratch = tmp_path / 's3-pr79-v1'; scratch.mkdir()
    monkeypatch.setattr(d, 'SCRATCH', scratch)
    with pytest.raises(ValueError, match='scratch_preexists'):
        d.parent(lambda *a, **kw: pytest.fail('child reached'))
    assert scratch.exists()


def test_finish_child_late_denial_and_sanitized_exception(capsys):
    guard = d.Audit()
    try: guard('socket.connect', ())
    except PermissionError: pass
    value = {'status': d.PASS}
    d.finish_child(value, guard)
    record = json.loads(capsys.readouterr().out[len(d.PREFIX):])
    assert record['status'] == d.load_guard.NETWORK
    exc = FileNotFoundError(2, 'missing', str(d.SCRATCH / 'tmp/file with spaces'))
    assert d.exception_record(exc, 'load')['filename']['path_category'] == 'diagnostic_scratch'


@pytest.mark.parametrize('error', [ValueError, PermissionError])
def test_failure_blocker_sanitizes_paths_with_spaces(error):
    value = d.failure_record(error(d.prior.CHECKPOINT + r': missing C:\private directory\secret name.bin'))
    assert value['status'] == d.prior.CHECKPOINT
    assert 'private directory' not in value['blocker'] and 'secret name' not in value['blocker']
    assert ':\\' not in value['blocker']


def test_durable_result_if_present():
    if not d.RESULT.exists(): pytest.skip('pre-live; never dispatch from tests')
    value = json.loads(d.RESULT.read_bytes())
    digest = value.pop('canonical_result_sha256')
    assert digest == d.canonical_hash(value) and value['runner_sha256'] == d.sha(Path(d.__file__))
    assert value['authority_flags'] == dict.fromkeys(d.prior.audit.FLAGS, False)
    assert value['execution_counts']['live_invocations'] == 1
    assert value['scratch_cleaned'] and value['identities_before'] == value['identities_after']
    assert value['identities_before']['checkpoint']['sha256'] == d.prior.CHECKPOINT_SHA
    assert not any(value['process_boundary'][k] for k in ('train_opened', 'held_out_opened', 'stage_a_opened'))
    assert value['execution_counts']['training_steps'] == value['execution_counts']['backward_calls'] == 0
    assert not value['execution_counts']['optimizer_constructed'] and not value['execution_counts']['scheduler_constructed']
    assert 'utterance' not in json.dumps(value) and ':\\' not in json.dumps(value)
    if value['status'] != d.PASS:
        assert 'exception' in value or 'transport_exception' in value
        return
    counts = value['execution_counts']
    assert counts['model_loads'] == counts['checkpoint_loads'] == counts['validation_passes'] == 1
    assert counts['validation_forward_batches'] == 34
    assert counts['shared_model_decisions'] == counts['historical_decoder_calls'] == counts['s3_decoder_calls'] == 540
    assert counts['additional_model_forwards_for_second_decoder'] == 0
    assert value['restored_parameter_hashes'] == value['parameter_hashes_after'] == d.prior.PARAMETERS
    accepted = d.prior.accepted_evidence()
    assert d.prior.reproduction(value['historical'], accepted['validation']) == value['historical_reproduction']
    assert d.prior.safety(value['s3']) and value['safety_gate_passed']
    assert [len(x) for x in value['batch_case_ids']] == [16] * 33 + [12]
    assert len(value['eligible_case_ids']) == 540 and len(value['blocked_case_ids']) == 60
    assert value['audit']['first_denial'] is None
    analysis = value['analysis']
    assert sum(analysis['transition_counts'].values()) == 540
    assert sum(analysis['play_failure_counts'].values()) == sum(analysis['gold_play_transitions'].values()) == 300
    assert analysis['unknown_rows'] == 240 and not analysis['unknown_safety_error_ids']
    assert len(analysis['historical_eleven_plays']) == 11
    for slot, summary in analysis['slots'].items():
        assert summary['presence'] + summary['null_on_gold_play'] == 300
        gap = analysis['structural_oracle_gap'][slot]
        assert gap['learned_exact'] == summary['exact'] and gap['gap'] == gap['gold_bio_ceiling'] - summary['exact']
