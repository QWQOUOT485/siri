"""CPU-only PR91 structural diagnosis and explicit transport boundaries."""
import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as N

import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import local_ai_stage_b_laya_span_typed_diagnosis_v2 as d


@pytest.mark.parametrize('category,tags,offsets,text',[
    ('track_labels_absent',[0],[(0,3)],'abc'),
    ('track_orphan_inside_only',[2],[(0,3)],'abc'),
    ('track_multiple_begin_or_multiple_spans',[1,1],[(0,3),(4,7)],'abc def'),
    ('track_begin_broken_or_discontinuous',[2,1],[(0,3),(4,7)],'abc def'),
    ('track_invalid_selected_offset',[1],[None],'abc'),
    ('track_conflict_with_selected_optional',[1,3],[(0,4),(3,7)],'abcdefg'),
    ('track_forbidden_or_empty_after_tightening',[1],[(0,3)],'cmd'),
    ('track_other_decoder_rejection',[0,0,1],[(5,6),(0,1),(1,4)],'abcdefg'),
    ('track_other_decoder_rejection',[1,2],[(0,4),(3,7)],'abcdefg')])
def test_frozen_taxonomy_all_categories(category,tags,offsets,text):
    result=d.taxonomy(tags,offsets,text)
    assert result['category']==category and result['trace']['code']
    if category=='track_other_decoder_rejection':
        assert result['trace']['code'] in ('unselected_o_order_reversal','selected_track_offset_overlap')


def test_taxonomy_rejects_unexplained_and_accepted_span():
    with pytest.raises(ValueError,match=d.TAXONOMY):d.taxonomy([1],[(0,3)],'abc')
    with pytest.raises(ValueError,match=d.TAXONOMY):d.taxonomy([1],[None,None],'abc')


def record(case='synthetic',gold=0,pred=0,typed=0,prob=.6,intent='spotify_play_track'):
    return dict(case_id=case,language_tag='mixed',gold_intent=intent,typed_index=typed,
        typed_play_probability=prob,typed_logits=[prob,1-prob],
        typed_argmax_margin=2*prob-1,validity_probability=.6,user_token_count=1,
        gold_bio_label_ids=[gold],masked_predicted_bio_label_ids=[pred],token_offsets=[(0,3)])


def test_confusion_7x7_and_span_metrics():
    values=[record(gold=1,pred=1),record(gold=2,pred=0),record(gold=0,pred=1)]
    report=d.confusion(values)
    assert len(report['matrix'])==7 and all(len(row)==7 for row in report['matrix'])
    assert report['matrix'][1][1]==report['matrix'][2][0]==report['matrix'][0][1]==1
    assert report['user_token_total']==3
    assert report['classes']['B-TRACK']==dict(support=1,predicted=2,true_positive=1,
        false_positive=1,false_negative=0,precision=.5,recall=1.,f1=2/3)
    assert report['classes']['I-TRACK']['false_negative']==1
    assert report['micro']['precision']==.5 and report['micro']['recall']==.5


def test_gold_span_coverage_contrasts_o_wrong_slot_partial_and_exact():
    row=N(case_id='a',utterance='abcdef',expected=N(track=N(start=0,end=6),artist=None,album=None))
    records=[]
    for i,pred in enumerate(([0,0],[1,0],[1,2],[3,4])):
        rec=record(case='a',gold=1,pred=pred[0]);rec['case_id']=str(i)
        rec['gold_bio_label_ids']=[1,2];rec['masked_predicted_bio_label_ids']=pred
        rec['token_offsets']=[(0,3),(3,6)];records.append(rec)
    report=d.span_coverage(records,'track',{str(i):row for i in range(4)})
    assert report['gold_rows']==4 and report['all_gold_tokens_o']==1
    assert report['partial_correct_slot']==1 and report['exact_gold_bio_sequence']==1
    assert report['all_gold_tokens_wrong_slot']==1 and report['correct_b_broken_i']==1


def test_quantiles_and_margin_edges():
    values=[.1,.3,.5,.7,.9]
    assert d.quantile(values,.25)==.3 and d.quantile(values,.5)==.5 and d.quantile(values,.95)==.86
    assert d.margins([.499,.47,.43,.35,.25],True)=={
        '0.00-0.02':1,'0.02-0.05':1,'0.05-0.10':1,'0.10-0.20':1,'>0.20':1}
    assert d.margins([.5,.53,.57,.65,.75],False)=={
        '0.00-0.02':1,'0.02-0.05':1,'0.05-0.10':1,'0.10-0.20':1,'>0.20':1}
    x=d.distribution([record(prob=v) for v in values]);assert x['below_0_5']==2 and x['at_or_above_0_5']==3


def test_optional_structural_ignores_track_requirement_but_keeps_offset_and_forbidden_gates():
    assert d.optional_structural([3,4],[(0,3),(3,6)],'abcdef','artist')
    assert not d.optional_structural([4],[(0,3)],'abc','artist')
    assert not d.optional_structural([3,0,4],[(0,3),(3,4),(4,6)],'abcdef','artist')
    assert not d.optional_structural([3],[(0,3)],'cmd','artist')
    assert not d.optional_structural([3,1],[(0,4),(3,7)],'abcdefg','artist')


@pytest.mark.parametrize('bad',[r'C:\private directory\secret.txt','https://x','播放晴天'])
def test_sanitization_rejects_absolute_paths_or_utterance(bad):
    with pytest.raises(ValueError,match=d.DATA):d.sanitization_check({'value':bad},['播放晴天'])
    with pytest.raises(ValueError,match=d.DATA):d.sanitization_check({'utterance':'hidden'})


def test_user_record_keeps_only_user_state_offsets_labels():
    row=N(case_id='synthetic',language_tag='mixed',utterance='abc',expected=N(intent='spotify_play_track'))
    item={'user_state_mask':[False,True,False],'token_offsets':[None,(0,3),None],
          'bio_labels':[-100,1,-100]}
    result=d.user_record(row,item,0,.7,.6,[6,1,6],[.7,.3])
    assert result['masked_predicted_bio_label_ids']==result['gold_bio_label_ids']==[1]
    assert result['token_offsets']==[(0,3)] and result['user_token_count']==1
    assert 'utterance' not in json.dumps(result)
    with pytest.raises(ValueError,match=d.DATA):d.user_record(row,item,0,.7,.6,[6],[.7,.3])


def test_pr88_exact_reproduction_and_drift_gate():
    value=json.loads(d.PR88.read_bytes())
    rows=[N(case_id=x['case_id']) for x in value['shared_decisions']]
    old=[{k:v for k,v in x.items() if k!='case_id'} for x in value['historical']['predictions']]
    new=[{k:v for k,v in x.items() if k!='case_id'} for x in value['s3']['predictions']]
    decisions=value['shared_decisions']
    proof=d.reproduce(rows,old,new,decisions,value)
    assert proof['exact_decision_prediction_matches']==540 and not any(proof['mismatch_case_ids'].values())
    changed=[dict(x) for x in decisions];changed[0]['typed_index']=1-changed[0]['typed_index']
    with pytest.raises(ValueError,match=d.REPRODUCTION):d.reproduce(rows,old,new,changed,value)
    drift=[dict(x) for x in decisions];drift[0]['typed_play_probability']+=1e-7
    assert d.reproduce(rows,old,new,drift,value)['max_absolute_probability_delta']['typed_play_probability']>0
    changed=[dict(x) for x in decisions];changed[0]['validity_probability']=.1
    with pytest.raises(ValueError,match=d.REPRODUCTION):d.reproduce(rows,old,new,changed,value)
    changed=[dict(x) for x in old];changed[0]['intent']='play' if old[0]['intent']=='unknown' else 'unknown'
    with pytest.raises(ValueError,match=d.REPRODUCTION):d.reproduce(rows,changed,new,decisions,value)
    changed=[dict(x) for x in new];changed[0]['intent']='play' if new[0]['intent']=='unknown' else 'unknown'
    with pytest.raises(ValueError,match=d.REPRODUCTION):d.reproduce(rows,old,changed,decisions,value)


def synthetic_540():
    accepted=json.loads(d.PR88.read_bytes())
    import local_ai_stage_b_laya_small_adaptation as hist
    real_rows=hist.parse_validation(d.prior.VALIDATION.read_bytes())
    eligible=hist.eligible_rows(real_rows,540,60)
    ids=accepted['analysis']['play_failure_case_ids']['typed_not_play']
    token_records=[]
    for row in eligible:
        is_play=row.expected.intent=='spotify_play_track'
        rec=record(case=row.case_id,gold=1 if is_play else 0,pred=0,typed=1 if row.case_id in ids else 0,
            prob=.4 if row.case_id in ids else .6,intent=row.expected.intent)
        rec['language_tag']=row.language_tag
        token_records.append(rec)
    predictions=[dict(d.prior.research.s3_decoder.NULL) for _ in eligible]
    return eligible,token_records,predictions,accepted,ids


def test_70_counterfactual_and_overlap_on_synthetic_all_o():
    eligible,token_records,predictions,accepted,ids=synthetic_540()
    diagnosis=d.diagnose(eligible,token_records,predictions,accepted)
    assert diagnosis['typed_gate_counterfactual']['counts']['structurally_invalid_or_missing_track']==70
    assert diagnosis['typed_gate_counterfactual']['counts']['structurally_valid_track']==0
    assert diagnosis['track_taxonomy']['counts']['track_labels_absent']==218
    assert diagnosis['track_taxonomy']['total']==218
    assert diagnosis['typed_vs_span_overlap_matrix']['typed_not_play']['invalid_or_missing_track']==70
    assert diagnosis['bio_confusion']['all']['user_token_total']==300
    assert diagnosis['gold_span_coverage']['track']['all']['gold_rows']==300


def test_bio_structure_independent_of_actual_validity_in_typed70():
    rows,records,predictions,accepted,ids=synthetic_540()
    case=ids[0];i=next(i for i,r in enumerate(rows) if r.case_id==case)
    gold=rows[i].expected.track
    records[i]['masked_predicted_bio_label_ids']=[1]
    records[i]['token_offsets']=[(gold.start,gold.end)]
    records[i]['validity_probability']=.1
    report=d.diagnose(rows,records,predictions,accepted)
    cf=report['typed_gate_counterfactual']['counts']
    assert cf['structurally_invalid_or_missing_track']==69
    assert cf['structurally_valid_track']==cf['structurally_exact_track']==1
    assert cf['typed_only_would_emit_track']==0
    assert cf['validity_blocked_structurally_valid']==1
    assert report['typed_vs_span_overlap_matrix']['typed_not_play']['valid_track']==1


def test_audit_exact_read_only_and_new_scratch(monkeypatch,tmp_path):
    scratch=tmp_path/'span-typed-v2';monkeypatch.setattr(d,'SCRATCH',scratch)
    guard=d.Audit()
    for name,path in [('validation',d.prior.VALIDATION),('pr79_checkpoint',d.prior.CHECKPOINT_PATH),('pr88_evidence',d.PR88)]:
        guard('open',(str(path),'rb',os.O_RDONLY));assert guard.allowed_reads[name]==1
        with pytest.raises(PermissionError):guard('open',(str(path),'wb',os.O_WRONLY))
    assert guard.first_denial
    with pytest.raises(PermissionError):guard.check()
    other=d.Audit();other('os.mkdir',(str(scratch/'tmp'),));assert other.counts['allowed_scratch_events']==1
    with pytest.raises(PermissionError):other('socket.connect',())


@pytest.mark.parametrize('event',('os.rename','os.link','os.symlink'))
def test_protected_destination_and_alias_read_rejected(monkeypatch,event):
    guard=d.Audit()
    with pytest.raises(PermissionError,match='STOP_LAYA_SPAN_TYPED_V2_PROTECTED_WRITE'):
        guard(event,(str(d.SCRATCH/'tmp/a'),str(d.pinned.MODEL/'foo')))
    original=Path.resolve
    monkeypatch.setattr(Path,'resolve',lambda self,*a,**kw: d.PR88.parent/'other.json' if self==d.PR88 else original(self,*a,**kw))
    with pytest.raises(PermissionError):d.Audit()('open',(str(d.PR88),'rb',os.O_RDONLY))


def test_parent_one_raw_child_transport_and_cleanup(monkeypatch,tmp_path):
    scratch=tmp_path/'span-typed-v2';monkeypatch.setattr(d,'SCRATCH',scratch)
    monkeypatch.setattr(d,'RESULT',tmp_path/'absent.json')
    monkeypatch.setattr(d.pinned,'PYTHON',Path(sys.executable))
    called=[]
    def run(argv,**kw):
        called.append(argv)
        assert argv[1:4]==['-B','-X','utf8'] and argv[-1]=='--child' and kw['text'] is False
        assert 'PYTHONPATH' not in kw['env'] and kw['env']['GIT_OPTIONAL_LOCKS']=='0'
        assert all(kw['env'][k]==str(scratch/v) for k,v in d.CACHE_BINDINGS.items())
        raise subprocess.TimeoutExpired(argv,600)
    value=d.parent(run)
    assert len(called)==1 and value['status']==d.BLOCKER and value['execution_counts']['live_invocations']==1
    assert value['scratch_cleaned'] and not scratch.exists()
    assert value.pop('canonical_result_sha256')==d.canonical_hash(value)


def test_source_static_one_forward_no_training_paths():
    text=Path(d.__file__).read_text(encoding='utf-8');tree=ast.parse(text)
    calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
    assert calls.count('laya.load')==calls.count('torch.load')==calls.count('historical.forward')==1
    assert not any(x.endswith(('.backward','.step')) or '.optim.' in x for x in calls)
    assert 'with torch.no_grad()' in text and 'module.requires_grad_(False)' in text
    assert 'map_location=\'cpu\', weights_only=True' in text
    assert text.index("result['pr88_reproduction']") < text.index("result['diagnosis']")


@pytest.mark.parametrize('label',(d.REPRODUCTION,d.TAXONOMY,d.DATA,d.CHECKPOINT,d.RESTORE,d.DEVICE,
    'STOP_LAYA_SPAN_TYPED_V2_PROTECTED_WRITE','STOP_LAYA_SPAN_TYPED_V2_UNEXPECTED_WRITE','STOP_LAYA_SPAN_TYPED_V2_NETWORK'))
def test_specific_stop_label_and_sanitized_blocker(label):
    value=d.failure_record(ValueError(label+r':C:\private directory\secret.txt'))
    assert value['status']==label and 'private directory' not in value['blocker']


def test_durable_if_present():
    if not d.RESULT.exists():pytest.skip('pre-live; tests never dispatch live mode')
    value=json.loads(d.RESULT.read_bytes());digest=value.pop('canonical_result_sha256')
    assert digest==d.canonical_hash(value) and value['runner_sha256']==d.sha(Path(d.__file__))
    assert value['execution_counts']['live_invocations']==1
    if value['status']!=d.PASS:return
    assert value['pr88_reproduction']['exact_decision_prediction_matches']==540
    assert value['diagnosis']['track_taxonomy']['total']==218
    assert sum(map(sum,value['diagnosis']['bio_confusion']['all']['matrix']))==value['diagnosis']['bio_confusion']['all']['user_token_total']
    assert value['diagnosis']['typed_gate_counterfactual']['exact_pr88_case_id_set_equal']
    assert sum(x['valid_track']+x['invalid_or_missing_track'] for x in value['diagnosis']['typed_vs_span_overlap_matrix'].values())==300
    assert value['identities_before']==value['identities_after'] and value['scratch_cleaned']
    assert value['execution_counts']['validation_forward_batches']==34
    assert value['execution_counts']['training_steps']==value['execution_counts']['backward_calls']==0
    assert not value['execution_counts']['optimizer_constructed']
    d.sanitization_check(value)


class StubGuard:
    allowed_reads = {'validation': 0}
    first_denial = None

    def summary(self):
        return {'synthetic': True}


def synthetic_transport_result():
    return {'schema': 'laya-span-typed-diagnosis-v2', 'status': d.PASS,
        'scratch_created': True, 'execution_counts': {'live_invocations': 1}}


def test_explicit_transport_success_and_parent_parse(monkeypatch):
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(d.sys, 'stdout', out)
    monkeypatch.setattr(d.sys, 'stderr', err)
    assert d.emit_child_result(synthetic_transport_result(), StubGuard()) == 0
    summary, parsed = d.parse_child_result(N(returncode=0, stdout=out.getvalue().encode(), stderr=err.getvalue().encode()))
    assert summary['classifier'] == 'TRANSPORT_OK' and summary['stdout_marker_count'] == 1
    assert summary['child_stderr_retained'] and summary['stderr_transport_error'] is None
    assert parsed['transport_version'] == 'explicit-v2'
    assert parsed['primary_result_emitted_from_atexit'] is False
    assert parsed['transport_stage'] == 'stdout_flush_completed'
    assert 'atexit.register' not in Path(d.__file__).read_text(encoding='utf-8')


@pytest.mark.parametrize('failure',[False,True])
def test_actual_v2_transport_in_synthetic_subprocess(failure):
    source = '''
import sys
sys.path.insert(0, 'scripts')
import local_ai_stage_b_laya_span_typed_diagnosis_v2 as d
class Guard:
    allowed_reads = {'validation': 0}
    first_denial = None
    def summary(self): return {'synthetic': True}
result = {'schema':'laya-span-typed-diagnosis-v2','status':d.PASS,
          'scratch_created':True,'execution_counts':{'live_invocations':1}}
if sys.argv[1] == 'fail': result['raw_path'] = 'synthetic'
raise SystemExit(d.emit_child_result(result, Guard()))
'''
    env=os.environ.copy()
    env.pop('PYTHONPATH',None)
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    child=subprocess.run([sys.executable,'-B','-X','utf8','-c',source,
        'fail' if failure else 'healthy'],cwd=ROOT,env=env,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False,check=False)
    summary,parsed=d.parse_child_result(child)
    assert child.returncode == (2 if failure else 0)
    assert summary['classifier'] == ('NONZERO_CHILD_EXIT' if failure else 'TRANSPORT_OK')
    assert summary['stderr_transport_error']['stage'] == 'sanitization' if failure else parsed['status'] == d.PASS


@pytest.mark.parametrize('fault,stage',[
    ('sanitize','sanitization'),('hash','canonical_hash'),('nan','json_serialization'),
    ('object','json_serialization'),('write','stdout_write'),('flush','stdout_flush')])
def test_explicit_transport_fault_returns_nonzero_envelope(monkeypatch,fault,stage):
    class Broken(io.StringIO):
        def write(self, value):
            if fault == 'write': raise OSError('synthetic_write')
            return super().write(value)
        def flush(self):
            if fault == 'flush': raise OSError('synthetic_flush')
            return super().flush()
    out, err = Broken(), io.StringIO()
    monkeypatch.setattr(d.sys, 'stdout', out)
    monkeypatch.setattr(d.sys, 'stderr', err)
    result = synthetic_transport_result()
    if fault == 'sanitize': result['raw_path'] = 'synthetic'
    if fault == 'hash': monkeypatch.setattr(d, 'canonical_hash', lambda value: (_ for _ in ()).throw(RuntimeError('synthetic_hash')))
    if fault in ('nan','object'):
        result['probabilities'] = [float('nan') if fault == 'nan' else object()]
        monkeypatch.setattr(d, 'canonical_hash', lambda value: '0'*64)
    assert d.emit_child_result(result, StubGuard()) == 2
    summary, parsed = d.parse_child_result(N(returncode=2, stdout=b'', stderr=err.getvalue().encode()))
    assert parsed is None and summary['classifier'] == 'NONZERO_CHILD_EXIT'
    assert summary['stderr_transport_error']['stage'] == stage
    assert summary['stderr_transport_error']['sanitized_message'] in (
        'redacted','synthetic_hash','synthetic_write','synthetic_flush',d.DATA+':sensitive_key')
    assert 'Traceback' not in err.getvalue()


def test_parent_transport_rejects_corrupt_markers_without_raw_stderr():
    p=synthetic_transport_result();p['canonical_result_sha256']=d.canonical_hash(p)
    marker=(d.PREFIX+json.dumps(p)).encode()
    cases=[(b'',b'C:\\private\\secret',0,'MISSING_MARKER'),
           (marker+b'\n'+marker,b'',0,'DUPLICATE_MARKER'),
           (d.PREFIX.encode()+b'{',b'',0,'MALFORMED_JSON'),
           (d.PREFIX.encode()+b'{}',b'',0,'CHILD_SCHEMA_INVALID'),
           (d.PREFIX.encode()+json.dumps({**p,'canonical_result_sha256':'0'*64}).encode(),b'',0,'BAD_CANONICAL_HASH')]
    for stdout,stderr,rc,want in cases:
        summary, parsed=d.parse_child_result(N(returncode=rc,stdout=stdout,stderr=stderr))
        assert parsed is None and summary['classifier']==want
        assert 'private' not in json.dumps(summary)


def test_validity_auc_and_typed_margin_are_descriptive():
    assert d.auc_with_ties([.7,.8],[.2,.3])==1.0
    assert d.auc_with_ties([.5],[.5])==.5
    a=[record(prob=.7) for _ in range(2)]
    b=[record(prob=.3,intent='unknown') for _ in range(2)]
    for group,value in ((a,.7),(b,.3)):
        for row in group:row['validity_probability']=value
    report=d.validity_report(a,b)
    assert report['descriptive_auroc']==1.0
    assert report['groups']['gold_play']['below_0_5']==0
    assert d.distribution(a)['signed_argmax_margin']['mean']==pytest.approx(.4)
