"""Pure CPU design tests; no real tokenizer/model/accelerator required."""
import ast
import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import local_ai_stage_b_laya_span_seam_design as s


@pytest.mark.parametrize('case', s.safety_cases(), ids=lambda c: c['name'])
def test_adversarial_safety_matrix(case):
    c = case
    output = s.isolated(c['labels'], c['mask'], c['offsets'], c['text'], trim=True)
    assert output == c['expected']
    for slot in s.SLOTS:
        span = output[slot]
        if span is not None:
            ids = [i for i, tag in enumerate(c['labels']) if s.owner(tag) == slot]
            a, b = c['offsets'][ids[0]][0], c['offsets'][ids[-1]][1]
            assert a <= span['start'] < span['end'] <= b
            assert all(v.isspace() for v in c['text'][a:span['start']] + c['text'][span['end']:b])
            assert c['text'][span['start']:span['end']] == c['text'][a:b].strip()


def test_full_matrix_and_false_flags():
    assert s.check_safety()['passed'] == 24
    assert len(s.audit.FLAGS) == 6 and not any(s.audit.FLAGS.values())


def test_o_overlap_isolation_is_not_order_repair():
    labels, mask = [0, 0, 1], [True] * 3
    offsets = [(0, 1), (0, 2), (3, 6)]
    assert s.audit.strict_decode(0, 1., labels, mask, offsets, 'xx abc') == s.NULL
    assert s.isolated(labels, mask, offsets, 'xx abc')['track'] == {'start': 3, 'end': 6}
    for invalid in [[(1, 2), (0, 1), (3, 6)], [(0, 2), (0, 1), (3, 6)]]:
        assert s.isolated(labels, mask, invalid, 'xx abc') == s.NULL
    assert s.current_rejection(labels, mask, offsets, 'xx abc') == {
        'reason': 'token_offset_ordering', 'token_index': 1, 'previous_index': 0,
        'previous_slot': 'O', 'slot': 'O', 'previous_offset': [0, 1], 'offset': [0, 2]}


@pytest.mark.parametrize('text', ['https://example.test', 'spotify:track:123', r'C:\bad', 'powershell'])
def test_no_provider_or_execution_string(text):
    assert s.isolated([1], [True], [(0, len(text))], text, trim=True) == s.NULL


def test_invalid_optional_offsets_isolate_but_invalid_o_fails():
    for tag in (3, 5):
        result = s.isolated([1, tag], [True, True], [(0, 3), (99, 100)], 'abc def')
        assert result['intent'] == 'play' and result[s.owner(tag)] is None
    assert s.isolated([1, 0], [True, True], [(0, 3), (99, 100)], 'abc def') == s.NULL


@pytest.mark.parametrize('residual', [(-1, 0), (4, 0), (0, 4), (3, 3), (False, 0), None])
def test_residual_out_of_range_fail_closed(residual):
    assert s.isolated([1], [True], [(0, 4)], 'abcd', residuals={'track': residual}) == s.NULL


def test_residual_exact_substring_and_optional_failure():
    result = s.isolated([1, 3], [True, True], [(0, 4), (5, 9)], 'abcd efgh',
                        residuals={'track': (1, 1), 'artist': (-1, 0)})
    assert result == {'intent': 'play', 'track': {'start': 1, 'end': 3}, 'artist': None, 'album': None}


@pytest.mark.parametrize('labels,reason', [([2], 'missing_track_begin'), ([1, 1], 'multiple_track_begin'),
    ([1, 0, 2], 'orphan_track_inside')])
def test_precise_rejection_trace(labels, reason):
    assert s.current_rejection(labels, [True]*len(labels), [(i, i+1) for i in range(len(labels))], 'abcdef')['reason'] == reason


def test_integer_gates_not_rounded():
    rates = {slot: {'exact': n} for slot, n in s.GATES.items()}
    assert s.passed(rates)
    for slot in s.SLOTS:
        reduced = {k: dict(v) for k, v in rates.items()}
        reduced[slot]['exact'] -= 1
        assert not s.passed(reduced)


def test_durable_result_and_s0_reproduction():
    p=s.audit.ROOT/'docs/local_ai/stage_b/evidence/LAYA_SPAN_SEAM_DESIGN_RESULT_2026-09-26.json'
    result=json.loads(p.read_bytes())
    expected=result.pop('canonical_result_sha256')
    assert s.audit.canonical_hash(result)==expected
    assert s.audit.canonical_hash(dict(reversed(list(result.items()))))==expected
    prior=json.loads((p.parent/'LAYA_SPAN_REPRESENTABILITY_AUDIT_2026-09-26.json').read_bytes())
    for split, report in result['splits'].items():
        for slot in s.SLOTS:
            assert report['rates']['S0'][slot]['exact']==prior['splits'][split]['slots'][slot]['current_label_roundtrip_exact']
            assert report['rates']['S0'][slot]['denominator']==s.DENOMS[split][slot]
        rows=s.audit.parse_split(split,s.audit.split_path(split).read_bytes())
        serialized=json.dumps(result,ensure_ascii=False)
        assert all(row.utterance not in serialized for row in rows)
    records=result['splits']['validation']['root_cause_records']
    assert len(records)==57 and len({r['case_id'] for r in records})==34
    assert all(r['reason']=='token_offset_ordering' and r['slot']==r['previous_slot']=='O' for r in records)
    assert sum(r['category']=='B' for r in records)==34
    assert result['splits']['validation']['root_cause_affected_slots']=={'track':34,'artist':5,'album':18}
    assert result['safety_matrix']['passed']==24
    assert result['preferred_design']=='S3' and not result['s4_evaluated']
    assert result['process_boundary']['opened_corpus_splits']==['train','validation']
    assert result['process_boundary']['protected_open_attempts']==0


def test_no_forbidden_operations_or_runtime_edits():
    source=Path(s.__file__).read_text(encoding='utf-8')
    forbidden={'AutoModel','forward','backward','AdamW','SGD','load','cuda','tensor','optimizer','run_validation',
               'verify_seal','artifact_inventory','select_device'}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call):
            name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            assert name not in forbidden
        if isinstance(node,ast.Import):assert all(n.name!='torch' for n in node.names)
    assert 'sys.addaudithook(audit.read_guard(opened, denied))' in source
