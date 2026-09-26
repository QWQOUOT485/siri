"""Tokenizer-only audit tests; no model tensors or accelerator use."""
import ast
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import local_ai_stage_b_laya_span_representability_audit as s
from test_local_ai_stage_b_laya_head_shape_smoke import CharTokenizer


@pytest.fixture(scope='module')
def rows():
    return {name:s.parse_split(name,s.split_path(name).read_bytes()) for name in s.SPLITS}


@pytest.mark.parametrize('name',['train','validation'])
def test_exact_sha_count_and_schema(name,rows,monkeypatch):
    raw=s.split_path(name).read_bytes()
    count,play,digest=s.SPLITS[name]
    assert len(rows[name])==count and hashlib.sha256(raw).hexdigest()==digest
    with pytest.raises(ValueError,match='sha_mismatch'):s.parse_split(name,raw+b'x')
    shortened=b'\n'.join(raw.splitlines()[:-1])
    monkeypatch.setitem(s.SPLITS,name,(count,play,hashlib.sha256(shortened).hexdigest()))
    with pytest.raises(ValueError,match='row_count'):s.parse_split(name,shortened)
    with pytest.raises(ValueError,match='not_authorized'):s.split_path('test')


def test_read_guard_rejects_protected_data_weights_and_network():
    opened=set();denied=[];guard=s.read_guard(opened,denied)
    for name in s.SPLITS:guard('open',(str(s.split_path(name)),'r',0))
    assert opened=={'train','validation'}
    paths=[s.ROOT/'artifacts/local_ai/stage_b/final_v1/held_out.jsonl',
           s.ROOT/'tests/fixtures/ai_intent_cases.json',s.ARTIFACT/'model.safetensors',
           Path('final.pt'),s.ROOT/'artifacts/unapproved.json']
    for path in paths:
        with pytest.raises(PermissionError,match='file_forbidden'):guard('open',(str(path),'rb',0))
    with pytest.raises(PermissionError):guard('socket.connect',())
    with pytest.raises(PermissionError):guard('socket.getaddrinfo',())
    with pytest.raises(ValueError,match='write_forbidden'):guard('open',(str(s.split_path('train')),'w',0))
    assert len(denied)==7


def test_local_only_tokenizer_factory(monkeypatch):
    calls=[]
    factory=SimpleNamespace(from_pretrained=lambda *a,**kw:calls.append((a,kw)) or 'tokenizer')
    monkeypatch.setitem(sys.modules,'transformers',SimpleNamespace(AutoTokenizer=factory))
    assert s.load_tokenizer()=='tokenizer'
    assert calls==[((str(s.ARTIFACT/'tokenizer'),),{'local_files_only':True})]


def test_current_renderer_and_decoder_oracle_exact(rows):
    row=next(r for r in rows['train'] if r.ai_scope=='supported' and r.expected.artist is not None and r.expected.album is not None)
    item=s.render(row,CharTokenizer(),{'max_len':1024,'head_max_len':256})
    labels=[tag if inside else 0 for tag,inside in zip(item['bio_labels'],item['user_state_mask'])]
    prediction=s.strict_decode(0,1.0,labels,item['user_state_mask'],item['token_offsets'],row.utterance)
    for slot in s.SLOTS:assert prediction[slot]==s.raw_span(getattr(row.expected,slot))


def test_any_contiguous_interval_no_partial_trim_or_gap():
    gold={'start':1,'end':4}
    assert s.any_interval(gold,[True,True,True],[(0,1),(1,2),(2,4)],4)==[1,2]
    assert s.any_interval(gold,[True,True],[(0,2),(2,4)],4) is None
    assert s.any_interval(gold,[True,False,True],[(1,2),None,(3,4)],4) is None
    assert s.any_interval(gold,[True,True],[(1,3),(2,4)],4) is None
    assert s.any_interval(gold,[True],[()],4) is None
    assert s.any_interval(gold,[True],[(1,9)],4) is None


def test_a_b_c_partition_alternate_interval():
    gold={'start':1,'end':4}
    interval=s.any_interval(gold,[True,True,True],[(0,1),(1,2),(2,4)],4)
    assert s.classify(gold,gold,interval)=='A'
    assert s.classify({'start':0,'end':4},gold,interval)=='B'
    assert s.classify({'start':0,'end':4},gold,None)=='C'
    with pytest.raises(ValueError):s.classify(gold,gold,None)


@pytest.mark.parametrize('text,current,gold,expected',[
    (' abc',{'start':0,'end':4},{'start':1,'end':4},'leading_whitespace_only'),
    ('abc ',{'start':0,'end':4},{'start':0,'end':3},'trailing_whitespace_only'),
    ('\u2003abc\t',{'start':0,'end':5},{'start':1,'end':4},'both_whitespace_only'),
    ('xabc',{'start':0,'end':4},{'start':1,'end':4},'non_whitespace_boundary_error'),
    ('abc',None,{'start':0,'end':3},'missing_or_multiple_span'),
    ('abc',{'start':0,'end':3},{'start':0,'end':3},'exact'),
])
def test_whitespace_diagnostic_not_scoring(text,current,gold,expected):
    assert s.whitespace_kind(text,current,gold)==expected


def test_all_span_denominators_unknown_targets_no_text(rows):
    reports={}
    for name in s.SPLITS:
        report,details=s.audit_split(rows[name],CharTokenizer(),{'max_len':1024,'head_max_len':256})
        reports[name]=report
        for slot,v in report['slots'].items():
            expected=sum(r.ai_scope=='supported' and r.expected.intent=='spotify_play_track'
                         and getattr(r.expected,slot) is not None for r in rows[name])
            assert v['denominator']==expected
            assert v['categories']=={'A':expected,'B':0,'C':0}
            assert v['boundary_alignment']['both_boundaries_exact']==expected
            assert sum(v['whitespace_mismatches'].values())==0
        serialized=json.dumps(report,ensure_ascii=False)
        assert 'utterance' not in serialized
        assert all(r.utterance not in serialized for r in rows[name])
    assert [reports['validation']['slots'][slot]['denominator'] for slot in s.SLOTS]==[300,126,204]
    assert reports['train']['supported_unknown_o_only_rows']==600
    assert reports['validation']['supported_unknown_o_only_rows']==240
    assert reports['train']['blocked_unrendered_null_target_rows']==300
    assert reports['validation']['blocked_unrendered_null_target_rows']==60


def test_pr79_cross_reference_exact11_not_rescore(rows):
    prior=s.read_prior()
    original=s.canonical_hash(prior)
    details={r.case_id:{'track':{'category':'A'}} for r in rows['validation'] if r.expected.track is not None}
    report=s.cross_reference(prior,rows['validation'],details)
    assert len(report)==11
    assert s.canonical_hash(prior)==original
    assert sum(r['start_delta']==-1 for r in report)==5
    assert sum(r['start_delta']==-1 and r['end_delta']==0 for r in report)==3
    assert 'utterance' not in json.dumps(report)


@pytest.mark.parametrize('representable,roundtrip,status',[(284,280,s.TRACK_STOP),(285,284,s.TARGET_STOP),(285,285,s.PASS),(300,300,s.PASS)])
def test_frozen95_gate(representable,roundtrip,status):
    report={'slots':{'track':{'denominator':300,'any_token_exact_representable':representable,'current_label_roundtrip_exact':roundtrip}}}
    assert s.decision(report)==status


def test_canonical_hash_and_all_six_false():
    assert s.canonical_hash({'a':1,'b':[2]})==s.canonical_hash({'b':[2],'a':1})
    assert len(s.FLAGS)==6 and all(v is False for v in s.FLAGS.values())
    with pytest.raises(ValueError):s.canonical_hash({'n':float('nan')})


def test_source_forbids_compute_and_protected_verifiers():
    source=Path(s.__file__).read_text(encoding='utf-8')
    tree=ast.parse(source)
    forbidden={'AutoModel','load','forward','backward','AdamW','SGD','child','parent','run_validation',
               'verified_data','verify_seal','artifact_inventory','select_device','cuda','tensor','zeros','ones'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Call):
            name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            assert name not in forbidden,name
        if isinstance(node,ast.Import):assert all(n.name!='torch' for n in node.names)
    assert 'local_files_only=True' in source
    assert 'from local_ai_stage_b_laya_small_adaptation import decode as strict_decode' in source
