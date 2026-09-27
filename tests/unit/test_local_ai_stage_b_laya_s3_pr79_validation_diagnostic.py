"""Synthetic/CPU diagnostic gates. Never invokes the live child."""
import ast
import copy
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace as N

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import local_ai_stage_b_laya_s3_pr79_validation_diagnostic as d


def proposal(intent='unknown', track=None, artist=None, album=None):
    return dict(intent=intent, track=track, artist=artist, album=album)


def row(case='synthetic', intent='spotify_play_track', language='mixed'):
    return N(case_id=case, ai_scope='supported', language_tag=language, utterance=' abc',
        expected=N(intent=intent, track=N(start=1,end=4) if intent != 'unknown' else None, artist=None, album=None))


def test_dual_actual_dispatch_identical_decisions_and_mask(monkeypatch):
    seen=[]; old=object(); new=object()
    def old_spy(*args):seen.append(args);return old
    def new_spy(*args):seen.append(args);return new
    monkeypatch.setattr(d.historical,'decode',old_spy)
    monkeypatch.setattr(d.research.s3_decoder,'decode',new_spy)
    mask=[False,True,True,False];offsets=[None,(0,2),(2,4),None]
    a,b,c=d.dual_decode([row()],[{'user_state_mask':mask,'token_offsets':offsets}],[0],[.8],[.9],[[99,1,2,99,7]])
    assert a==[old] and b==[new] and len(seen)==2
    assert seen[0]==seen[1]==(0,.9,[0,1,2,0],mask,offsets,' abc')
    assert seen[0][3] is seen[1][3] and seen[0][4] is seen[1][4]
    assert c==[{'case_id':'synthetic','typed_index':0,'typed_play_probability':.8,'validity_probability':.9}]


@pytest.mark.parametrize('scope',['deterministic_only','safety_only'])
def test_blocked_before_either_decoder(monkeypatch,scope):
    r=row();r.ai_scope=scope
    monkeypatch.setattr(d.historical,'decode',lambda *a:pytest.fail('decoder reached'))
    with pytest.raises(ValueError,match=d.DATA):d.dual_decode([r],[{}],[0],[1],[1],[[1]])


def test_short_labels_fail():
    with pytest.raises(ValueError,match='labels_short'):
        d.dual_decode([row()],[{'user_state_mask':[True,True]}],[0],[1],[1],[[1]])


def test_checkpoint_binding_matches_actual_reviewed_save():
    prior=d.accepted_evidence();binding=d.checkpoint_binding(prior)
    assert binding=={'config':json.loads(d.smoke.canonical_bytes(d.historical.CONFIG)),
        'seed':1729,'train_selection':prior['selection'],'identities':prior['identities_before']}
    source=inspect.getsource(d.historical.child)
    assert '"train_selection": manifest, "identities": before' in source
    assert prior['parameter_hashes_after']==d.PARAMETERS


@pytest.mark.parametrize('mutation',['extra','missing','schema','steps','bool_steps','binding'])
def test_checkpoint_payload_fail_closed(mutation):
    binding={'seed':1729}
    payload=dict(schema='laya-small-adaptation-final-v1',typed={},span={},validity={},optimizer=object(),completed_steps=189,binding=binding)
    d.validate_payload(payload,binding)
    if mutation=='extra':payload['encoder']={}
    elif mutation=='missing':del payload['optimizer']
    elif mutation=='schema':payload['schema']='other'
    elif mutation=='steps':payload['completed_steps']=188
    elif mutation=='bool_steps':payload['completed_steps']=True
    else:payload['binding']={'seed':1}
    with pytest.raises(ValueError,match=d.CHECKPOINT):d.validate_payload(payload,binding)


def test_checkpoint_wrong_path_rejected(tmp_path):
    with pytest.raises(ValueError,match=d.CHECKPOINT):d.checkpoint_identity(tmp_path/'final.pt')


def test_restore_named_states_and_ignored_optimizer():
    source=inspect.getsource(d.restore)
    assert "payload['optimizer']" not in source
    assert "payload['typed']" in source and "payload['span']" in source and "payload['validity']" in source
    assert 'strict=True' in source and 'saved.dtype == value.dtype' in source
    assert 'hashes == PARAMETERS' in source


def devices():
    return [{'index':0,'name':'AMD Radeon(TM) Graphics','architecture':'gfx1036','device_type':'cuda','total_memory_bytes':1},
        {'index':1,'name':'AMD Radeon RX 9070 XT','architecture':'gfx1201','device_type':'cuda','total_memory_bytes':2}]


def test_exact_device():assert d.select_device(devices())=='cuda:1'


@pytest.mark.parametrize('mutation',['cpu','nvidia','index','ambiguous','arch','missing'])
def test_device_fail_closed(mutation):
    values=devices()
    if mutation=='missing':values.pop()
    elif mutation=='ambiguous':values.append(values[1])
    else:values[1][{'cpu':'device_type','nvidia':'name','index':'index','arch':'architecture'}[mutation]]={'cpu':'cpu','nvidia':'RTX 3060','index':0,'arch':'gfx1036'}[mutation]
    with pytest.raises(ValueError,match=d.DEVICE):d.select_device(values)


@pytest.mark.parametrize('name',['train.jsonl','held_out.jsonl','ai_intent_cases.json','other.jsonl'])
def test_read_guard_forbidden_rows(name):
    opened=set();denied=[];guard=d.read_guard(opened,denied)
    with pytest.raises(PermissionError,match=d.DATA):guard('open',(str(d.ROOT/'artifacts'/name),'r',0))
    assert denied==['protected_rows'] and not opened


def test_read_guard_validation_only():
    opened=set();denied=[];guard=d.read_guard(opened,denied)
    guard('open',(str(d.VALIDATION),'rb',os.O_RDONLY))
    assert opened=={'validation'} and not denied


@pytest.mark.parametrize('event,args',[
    ('open',('file','wb',os.O_WRONLY)),('open',('file',None,os.O_CREAT)),
    ('os.remove',('file',)),('os.rename',('file','other')),('os.chmod',('file',0)),
    ('socket.connect',()),('socket.getaddrinfo',()),('os.mkdir',('nonexistent-diagnostic-dir',))])
def test_read_guard_mutations_network(event,args):
    with pytest.raises(PermissionError):d.read_guard(set(),[])(event,args)


def test_existing_directory_mkdir_is_no_creation(tmp_path):
    denied=[];d.read_guard(set(),denied)('os.mkdir',(str(tmp_path),0o777,-1))
    assert not denied and tmp_path.is_dir()


def test_historical_reproduction_exact_and_mismatch():
    expected=d.accepted_evidence()['validation']
    proof=d.reproduction(copy.deepcopy(expected),expected)
    assert proof['exact_matches']==540 and proof['aggregate_metrics_equal']
    changed=copy.deepcopy(expected);changed['predictions'][0]['track']={'start':1,'end':2}
    with pytest.raises(ValueError,match=d.REPRODUCTION):d.reproduction(changed,expected)
    changed=copy.deepcopy(expected);changed['track']['exact_span']['numerator']=1
    with pytest.raises(ValueError,match=d.REPRODUCTION):d.reproduction(changed,expected)


@pytest.mark.parametrize('field',['supported_unknown_recall','unknown_false_acceptance','blocked_before_renderer','eligibility_leakage','predicted_play_without_valid_track'])
def test_safety_exact(field):
    report=copy.deepcopy(d.accepted_evidence()['validation']);assert d.safety(report)
    if isinstance(report[field],dict):report[field]['numerator']+=1
    else:report[field]+=1
    assert not d.safety(report)


@pytest.mark.parametrize('old,new,key',[
    (proposal(),proposal(),'unchanged_unknown'),
    (proposal('play',{'start':1,'end':4}),proposal('play',{'start':1,'end':4}),'unchanged_play_exact_same_offsets'),
    (proposal(),proposal('play',{'start':1,'end':4}),'unknown_to_play'),
    (proposal('play',{'start':1,'end':4}),proposal(),'play_to_unknown'),
    (proposal('play',{'start':0,'end':4}),proposal('play',{'start':1,'end':4}),'play_to_play_offsets_changed')])
def test_transitions(old,new,key):assert d.transition(old,new)==key


@pytest.mark.parametrize('index,valid,prediction,bucket',[
    (1,.1,proposal(),'typed_not_play'),(0,.49,proposal(),'validity_below_threshold'),
    (0,.5,proposal(),'s3_track_invalid_or_missing'),
    (0,.9,proposal('play',{'start':0,'end':4}),'s3_track_present_not_exact'),
    (0,.9,proposal('play',{'start':1,'end':4},{'start':1,'end':2}),'s3_track_exact_optional_incomplete_or_wrong'),
    (0,.9,proposal('play',{'start':1,'end':4}),'full_semantic_exact')])
def test_mutually_exclusive_failure(index,valid,prediction,bucket):
    assert d.failure(row(),prediction,{'typed_index':index,'validity_probability':valid})==bucket


def test_synthetic_analysis_counts_offsets_and_oracle_gap():
    rows=[row(str(i),language='mixed' if i%2 else 'en') for i in range(300)]+[row(str(i),'unknown') for i in range(300,540)]
    old=[proposal('play',{'start':0,'end':4}) if i<11 else proposal() for i in range(540)]
    new=[proposal('play',{'start':1,'end':4}) if i<11 else proposal() for i in range(540)]
    decisions=[{'typed_index':0,'validity_probability':.9} for _ in rows]
    result=d.analysis(rows,old,new,decisions)
    assert sum(result['transition_counts'].values())==540
    assert sum(result['play_failure_counts'].values())==300
    assert result['play_failure_counts']['full_semantic_exact']==11
    assert result['play_failure_counts']['s3_track_invalid_or_missing']==289
    assert result['slots']['track']['start_delta']=={'0':11}
    assert len(result['slots']['track']['pure_leading_whitespace_corrections'])==11
    assert len(result['historical_eleven_plays'])==11
    assert result['structural_oracle_gap']['track']=={'learned_exact':11,'gold_bio_ceiling':297,'gap':286}
    assert not result['unknown_safety_error_ids']
    assert 'utterance' not in json.dumps(result)


def test_exact_real_validation_composition_and_historical_metric_wrapper():
    rows=d.historical.parse_validation(d.VALIDATION.read_bytes())
    composition=d.historical.validate_validation(rows)
    assert composition['rows']==600 and composition['groups']==100
    eligible=d.historical.eligible_rows(rows,540,60)
    expected=d.accepted_evidence()['validation']
    predictions=[{k:v for k,v in p.items() if k!='case_id'} for p in expected['predictions']]
    fake=[{'typed_play_probability':.5,'validity_probability':.5} for _ in eligible]
    actual=d.report(eligible,predictions,fake)
    assert d.reproduction(actual,expected)['aggregate_metrics_equal']
    assert [r.case_id for r in eligible]==expected['case_ids']


def test_parent_raw_bytes_one_child_and_hash(monkeypatch):
    monkeypatch.setattr(d,'preflight',lambda:None)
    result={'status':d.PASS};result['canonical_result_sha256']=d.canonical_hash(result)
    calls=[]
    def runner(args,**kwargs):
        calls.append((args,kwargs))
        return N(stdout=(d.PREFIX+json.dumps(result)).encode(),stderr=b'',returncode=0)
    assert d.parent(runner)==result and len(calls)==1
    args,kwargs=calls[0]
    assert args[1:4]==['-B','-X','utf8'] and args[-1]=='--child'
    assert kwargs['text'] is False and kwargs['env']['HF_HUB_OFFLINE']=='1'
    assert kwargs['env']['TRANSFORMERS_OFFLINE']=='1' and 'PYTHONPATH' not in kwargs['env']


def test_source_only_one_forward_and_one_cpu_weights_only_load():
    source=Path(d.__file__).read_text(encoding='utf-8');tree=ast.parse(source)
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call)]
    names=[ast.unparse(c.func) for c in calls]
    assert names.count('historical.forward')==names.count('laya.load')==names.count('torch.load')==1
    assert not any(name.endswith(('.backward','.step','.save')) or '.optim.' in name for name in names)
    assert not set(names)&{'historical.verified_data','historical.preflight','research.preflight','historical.run_validation','historical.child'}
    load=next(c for c in calls if ast.unparse(c.func)=='torch.load')
    assert {k.arg:ast.literal_eval(k.value) for k in load.keywords}=={'map_location':'cpu','weights_only':True}
    assert "range(0, 540, 16)" in source and "with torch.no_grad():" in source
    assert "module.eval()" in source and "module.requires_grad_(False)" in source
    assert 'sys.flags.utf8_mode == 1 and sys.dont_write_bytecode' in source
    assert 'uncommitted_prelive_source' in source and 'durable_result_already_exists' in source


def test_canonical_synthetic_hash():
    assert d.canonical_hash({'z':[1,2],'a':False})==d.canonical_hash({'a':False,'z':[1,2]})
    with pytest.raises(ValueError):d.canonical_hash({'loss':float('nan')})


def test_seven_historical_sources_unchanged():assert d.source_identity()==d.SOURCES


def test_durable_result_if_present():
    if not d.RESULT.exists():pytest.skip('no live result yet; never invokes live execution')
    value=json.loads(d.RESULT.read_bytes());digest=value.pop('canonical_result_sha256')
    assert d.canonical_hash(value)==digest
    assert value['identities_before']['runner_sha256']==d.sha(Path(d.__file__))
    assert value['authority_flags']==dict.fromkeys(d.audit.FLAGS,False)
    assert value['identities_before']==value['identities_after']
    assert value['model_before']==value['model_after']
    assert value['process_boundary']['opened_row_sources']==['validation']
    assert not any(value['process_boundary'][k] for k in ('train_rows_opened','held_out_rows_opened','stage_a_rows_opened'))
    counts=value['execution_counts']
    if value['status']!=d.PASS:
        assert value.get('blocker') and counts['live_invocations']==1
        assert counts['training_steps']==counts['backward_calls']==0
        assert counts['model_loads']<=1 and counts['checkpoint_loads']<=1
        return
    assert counts['live_invocations']==counts['model_loads']==counts['checkpoint_loads']==counts['validation_passes']==1
    assert counts['validation_forward_batches']==34
    assert counts['shared_model_decisions']==counts['historical_decoder_calls']==counts['s3_decoder_calls']==540
    assert counts['additional_model_forwards_for_second_decoder']==counts['training_steps']==counts['backward_calls']==0
    assert counts['optimizer_constructed'] is False
    if value['status']!=d.PASS:
        assert value.get('blocker');return
    assert value['restored_parameter_hashes']==value['parameter_hashes_after']==d.PARAMETERS
    assert d.reproduction(value['historical'],d.accepted_evidence()['validation'])==value['historical_reproduction']
    assert d.safety(value['s3'])
    assert sum(value['analysis']['transition_counts'].values())==540
    assert sum(value['analysis']['play_failure_counts'].values())==300
    assert value['analysis']['unknown_rows']==240 and not value['analysis']['unknown_safety_error_ids']
    for item in value['analysis']['structural_oracle_gap'].values():assert item['gap']==item['gold_bio_ceiling']-item['learned_exact']
    assert len(value['analysis']['historical_eleven_plays'])==11
    assert 'utterance' not in json.dumps(value)
