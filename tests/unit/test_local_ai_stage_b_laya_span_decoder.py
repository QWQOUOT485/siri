"""Real decoder safety and verifier gates; no model or GPU required."""
import ast
import json
import sys
from pathlib import Path

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import local_ai_stage_b_laya_span_decoder as decoder
import local_ai_stage_b_laya_span_seam_implementation_verify as verify
from test_local_ai_stage_b_laya_head_shape_smoke import CharTokenizer


@pytest.mark.parametrize('case', verify.design.safety_cases(), ids=lambda c:c['name'])
def test_reviewed_adversaries_on_real_decoder(case):
    c=case
    result=decoder.decode(0,1.0,c['labels'],c['mask'],c['offsets'],c['text'])
    assert result==c['expected']
    for slot in decoder.SLOTS:
        span=result[slot]
        if span is not None:
            ids=[i for i,t in enumerate(c['labels']) if decoder.owner(t)==slot]
            a,b=c['offsets'][ids[0]][0],c['offsets'][ids[-1]][1]
            assert a<=span['start']<span['end']<=b
            assert all(v.isspace() for v in c['text'][a:span['start']]+c['text'][span['end']:b])
            assert c['text'][span['start']:span['end']]==c['text'][a:b].strip()


@pytest.mark.parametrize('case',verify.implementation_cases(),ids=lambda c:c['name'])
def test_added_implementation_contract(case):
    assert decoder.decode(**{k:v for k,v in case.items() if k not in ('name','expected')})==case['expected']


@pytest.mark.parametrize('typed,validity',[(2,1),(-1,1),(True,1),(0,-.1),(0,float('inf')),(0,'1'),(0,True),(0,10**400),(0,-10**400)])
def test_closed_typed_and_finite_validity(typed,validity):
    assert decoder.decode(typed,validity,[1],[True],[(0,3)],'abc')==decoder.NULL


def test_half_threshold_is_unchanged():
    assert decoder.decode(0,.5,[1],[True],[(0,3)],'abc')['intent']=='play'


def test_historical_decoder_source_unchanged():
    assert verify.source_hashes()['local_ai_stage_b_laya_small_adaptation.py']==verify.HISTORICAL['local_ai_stage_b_laya_small_adaptation.py']


def test_design_source_unchanged():
    assert verify.source_hashes()['local_ai_stage_b_laya_span_seam_design.py']==verify.HISTORICAL['local_ai_stage_b_laya_span_seam_design.py']


def test_historical_mutation_fails_closed(monkeypatch):
    monkeypatch.setitem(verify.HISTORICAL,'local_ai_stage_b_laya_adapter.py','wrong')
    with pytest.raises(ValueError,match=verify.MUTATION):verify.source_hashes()


def test_exact_oracle_not_at_least():
    for split in verify.EXPECTED:
        verify.check_counts(split,verify.EXPECTED[split],verify.design.DENOMS[split])
        for delta in (-1,1):
            changed=dict(verify.EXPECTED[split]);changed['track']+=delta
            with pytest.raises(ValueError,match=verify.ORACLE):verify.check_counts(split,changed,verify.design.DENOMS[split])


def test_verifier_executes_real_decoder_and_design(monkeypatch):
    rows=verify.audit.parse_split('train',verify.audit.split_path('train').read_bytes())
    row=next(r for r in rows if r.ai_scope=='supported' and r.expected.intent=='spotify_play_track')
    calls=[]
    original=verify.design.isolated
    def reference(*a,**kw):
        calls.append('design');return original(*a,**kw)
    def drift(*a,**kw):
        calls.append('implementation');return dict(decoder.NULL)
    monkeypatch.setattr(verify.design,'isolated',reference)
    monkeypatch.setattr(decoder,'decode',drift)
    with pytest.raises(ValueError,match=verify.DRIFT):verify.verify_rows('train',[row],CharTokenizer(),{'max_len':1024,'head_max_len':256})
    assert calls==['design','implementation']


def test_safety_inventory_executes_real_decoder(monkeypatch):
    assert verify.safety_inventory()['implementation']['passed']==28
    monkeypatch.setattr(decoder,'decode',lambda *a,**kw:dict(decoder.NULL))
    with pytest.raises(ValueError,match=verify.BLOCKER):verify.safety_inventory()


def test_exact_forbidden_policy():
    assert decoder.adapter.FORBIDDEN_TEXT is verify.audit.adapter.FORBIDDEN_TEXT


def test_durable_result_identity_and_exact_parity():
    path=verify.audit.ROOT/'docs/local_ai/stage_b/evidence/LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json'
    data=json.loads(path.read_bytes());expected=data.pop('canonical_result_sha256')
    assert verify.audit.canonical_hash(data)==expected
    assert verify.audit.canonical_hash(dict(reversed(list(data.items()))))==expected
    assert data['historical_before']==data['historical_after']==verify.source_hashes()
    import hashlib
    for name,digest in data['source_hashes'].items():
        assert hashlib.sha256((verify.audit.ROOT/'scripts'/name).read_bytes()).hexdigest()==digest
    for split,report in data['splits'].items():
        assert report['implementation_exact']==report['design_exact']==verify.EXPECTED[split]
        n=verify.design.DENOMS[split]['track']
        assert report['parity']=={'total':n,'equal':n,'mismatches':0}
        rows=verify.audit.parse_split(split,verify.audit.split_path(split).read_bytes())
        serialized=json.dumps(data,ensure_ascii=False)
        assert all(r.utterance not in serialized for r in rows)
    assert len(data['splits']['validation']['retained_non_exact']['track'])==3
    assert len(data['splits']['validation']['retained_non_exact']['album'])==1
    assert data['process_boundary']['opened_corpus_splits']==['train','validation']
    assert data['process_boundary']['protected_open_attempts']==0
    assert len(data['authority_flags'])==6 and not any(data['authority_flags'].values())


def test_pure_decoder_and_no_forbidden_verifier_calls():
    source=Path(decoder.__file__).read_text(encoding='utf-8')
    assert 'seam_design' not in source and 'torch' not in source and 'residual' not in source
    verifier=Path(verify.__file__).read_text(encoding='utf-8')
    assert 'reference = design.isolated(*args, trim=True)' in verifier
    assert 'actual = implementation.decode(0, 1.0, *args)' in verifier
    forbidden={'AutoModel','forward','backward','AdamW','SGD','load','cuda','tensor','verify_seal','artifact_inventory'}
    for text in (source,verifier):
        for node in ast.walk(ast.parse(text)):
            if isinstance(node,ast.Call):
                name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
                assert name not in forbidden
