"""Synthetic filesystem/sanitizer gates; no model, GPU, dataset or checkpoint access."""
import ast
import errno
import inspect
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as N

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import local_ai_stage_b_laya_base_load_root_cause as d


@pytest.mark.parametrize('name',list(d.PROTECTED_ROOTS))
def test_protected_categories(name):
    assert d.category(d.PROTECTED_ROOTS[name]/'example.tmp')['path_category']==name


def test_scratch_and_outside_categories():
    assert d.category(d.SCRATCH/'tmp/a')=={'path_category':'diagnostic_scratch','relative_path':'tmp/a'}
    assert d.category(d.SCRATCH.parent/'other/a')['path_category']=='outside_scratch'
    assert d.category(d.SCRATCH/'../escape')['path_category']=='outside_scratch'


@pytest.mark.parametrize('event',['open','os.mkdir','os.chmod','os.remove','os.rmdir','os.truncate','os.utime','os.rename','os.link','os.symlink'])
@pytest.mark.parametrize('root',list(d.PROTECTED_ROOTS.values()))
def test_protected_write_rejected_and_latched(event,root):
    guard=d.Audit();path=str(root/'example')
    args=(path,'wb',os.O_WRONLY) if event=='open' else (path,str(d.SCRATCH/'destination'))
    with pytest.raises(PermissionError,match=d.PROTECTED):guard(event,args)
    assert guard.counts['denied_protected_events']==1
    with pytest.raises(PermissionError,match=d.PROTECTED):guard.check()
    first=dict(guard.first_denial)
    with pytest.raises(PermissionError):guard('socket.connect',())
    assert guard.first_denial==first


@pytest.mark.parametrize('event',['open','os.mkdir','os.chmod','os.remove','os.rmdir','os.truncate','os.utime','os.rename','os.link','os.symlink'])
def test_scratch_write_allowed(event):
    guard=d.Audit();path=str(d.SCRATCH/'tmp/a')
    args=(path,'wb',os.O_WRONLY) if event=='open' else (path,str(d.SCRATCH/'tmp/b'))
    guard(event,args);guard.check()
    assert guard.counts['allowed_scratch_events']==1 and not guard.first_denial
    assert all(e['path_category']=='diagnostic_scratch' for e in guard.details)


@pytest.mark.parametrize('event',['open','os.mkdir','os.chmod','os.remove','os.rename','os.link','os.symlink','os.truncate'])
def test_outside_write_rejected(event,tmp_path):
    guard=d.Audit();path=str(tmp_path/'other')
    args=(path,'wb',os.O_WRONLY) if event=='open' else (str(d.SCRATCH/'tmp/a'),path) if event in ('os.rename','os.link','os.symlink') else (path,)
    with pytest.raises(PermissionError,match=d.OUTSIDE):guard(event,args)
    assert guard.counts['denied_outside_events']==1


def test_existing_directory_mkdir_outside_also_rejected(tmp_path):
    with pytest.raises(PermissionError,match=d.OUTSIDE):d.Audit()('os.mkdir',(str(tmp_path),))


@pytest.mark.parametrize('event',['socket.connect','socket.getaddrinfo'])
def test_network_rejected(event):
    guard=d.Audit()
    with pytest.raises(PermissionError,match=d.NETWORK):guard(event,())
    assert guard.counts['network_attempts']==1


@pytest.mark.parametrize('path',[d.ROOT/'artifacts/x',d.PRIMARY/'tests/fixtures/x',d.SCRATCH/'train.jsonl',d.SCRATCH/'validation.jsonl',d.SCRATCH/'held_out.jsonl',d.SCRATCH/'ai_intent_cases.json'])
def test_no_dataset_read(path):
    guard=d.Audit()
    with pytest.raises(PermissionError,match=d.DATA):guard('open',(str(path),'rb',os.O_RDONLY))
    assert guard.counts['dataset_open_attempts']==1


@pytest.mark.parametrize('path',[d.reviewed.CHECKPOINT_PATH,d.SCRATCH/'other.pt'])
def test_no_checkpoint_open(path):
    guard=d.Audit()
    with pytest.raises(PermissionError,match=d.CHECKPOINT):guard('open',(str(path),'rb',os.O_RDONLY))
    assert guard.counts['checkpoint_open_attempts']==1


def test_pinned_model_read_allowed():
    guard=d.Audit();guard('open',(str(d.pinned.MODEL/'model.safetensors'),'rb',os.O_RDONLY));guard.check()
    assert not guard.details


def test_file_not_found_sanitizer_and_traceback():
    try:
        error=FileNotFoundError(errno.ENOENT,'missing '+str(d.pinned.MODEL/'missing.bin'),str(d.pinned.MODEL/'missing.bin'))
        error.winerror=3;error.filename2=str(d.SCRATCH/'tmp/second')
        raise error
    except FileNotFoundError as exc:
        value=d.exception_record(exc,'laya_load')
    assert value['errno']==2 and value['winerror']==3 and value['class']=='FileNotFoundError'
    assert value['filename']=={'path_category':'pinned_model','basename':'missing.bin'}
    assert value['filename2']=={'path_category':'diagnostic_scratch','basename':'second'}
    assert value['frames'][-1]['function']=='test_file_not_found_sanitizer_and_traceback'
    assert all(set(f)=={'module_basename','function','line'} for f in value['frames'])
    assert str(d.pinned.MODEL) not in json.dumps(value) and ':\\' not in value['message']
    assert '<pinned_model>' in value['message']


def test_unknown_absolute_path_redacted():
    value=d.sanitized_message(r"failed C:\private\name\x.bin and \\server\share\secret.txt")
    assert 'private' not in value and 'server' not in value


def test_one_load_no_retry():
    calls=[];agent=object();counts={'laya_load_attempts':0,'laya_load_completed':0}
    def load(*a,**kw):calls.append((a,kw));return agent
    assert d.one_load(N(load=load),counts) is agent
    assert calls==[((str(d.pinned.MODEL),),{'device':'cuda:1'})]
    assert counts=={'laya_load_attempts':1,'laya_load_completed':1}
    with pytest.raises(ValueError,match='extra_load'):d.one_load(N(load=load),counts)
    assert len(calls)==1


def test_failed_load_attempt_counter():
    counts={'laya_load_attempts':0,'laya_load_completed':0}
    def fail(*a,**kw):raise FileNotFoundError('synthetic')
    with pytest.raises(FileNotFoundError):d.one_load(N(load=fail),counts)
    assert counts=={'laya_load_attempts':1,'laya_load_completed':0}


def test_audit_cap_and_total():
    guard=d.Audit()
    for i in range(250):guard('os.mkdir',(str(d.SCRATCH/str(i)),))
    assert len(guard.details)==200 and guard.counts['allowed_scratch_events']==250
    assert guard.summary()['counts_by_event']=={'os.mkdir':250}


def test_no_compute_training_checkpoint_dataset_call_paths():
    tree=ast.parse(Path(d.__file__).read_text(encoding='utf-8'))
    calls=[ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n,ast.Call)]
    assert calls.count('laya.load')==1
    assert not any(s.endswith(('.forward','.backward','.step')) or '.optim.' in s for s in calls)
    assert not set(calls)&{'torch.load','torch.save','historical.render','reviewed.no_compute_identity','reviewed.checkpoint_identity','pinned.parent','pinned.child','reviewed.preflight','smoke.new_heads'}
    assert 'pinned.residency' in calls
    source=inspect.getsource(d.child)
    assert source.index('guard.check()')<source.index('agent = one_load')
    assert source.index('agent = one_load')<source.index('guard.check()',source.index('agent = one_load'))
    assert 'module.' not in source


def test_cache_bindings_complete_and_scratch_only():
    assert set(d.CACHE_BINDINGS)=={'TMP','TEMP','TMPDIR','TORCHINDUCTOR_CACHE_DIR','TRITON_CACHE_DIR','HF_HOME','HF_HUB_CACHE','TRANSFORMERS_CACHE','XDG_CACHE_HOME'}
    assert all(d.category(d.SCRATCH/p)['path_category']=='diagnostic_scratch' for p in d.CACHE_BINDINGS.values())


def test_finish_child_preserves_denial_and_false_finding(capsys):
    guard=d.Audit();guard.stage='laya_load'
    try:guard('os.mkdir',(str(d.PRIMARY),))
    except PermissionError:pass
    value={'status':d.PASS,'identities_before':{},'identities_after':{}}
    d.finish_child(value,guard)
    record=json.loads(capsys.readouterr().out[len(d.PREFIX):])
    assert record['status']==d.PROTECTED and record['pr86_global_write_guard_regression_supported'] is False
    digest=record.pop('canonical_result_sha256');assert digest==d.canonical_hash(record)


def test_durable_result_if_present():
    if not d.RESULT.exists():pytest.skip('pre-live; no live execution from tests')
    v=json.loads(d.RESULT.read_bytes());digest=v.pop('canonical_result_sha256');assert digest==d.canonical_hash(v)
    assert v['runner_sha256']==d.sha(Path(d.__file__))
    assert v['authority_flags']==dict.fromkeys(d.FLAGS,False)
    assert v['execution_counts']['live_invocations']==1 and v['execution_counts']['laya_load_attempts']<=1
    assert not v['checkpoint_opened'] and not v['dataset_opened']
    assert all(v['execution_counts'][k]==0 for k in ('checkpoint_loads','dataset_passes','forward_calls','training_steps','backward_calls'))
    assert v['identities_before']==v['identities_after']
    assert ':\\' not in json.dumps(v) and ':/' not in json.dumps(v)
    if v['status']==d.PASS:
        assert v['execution_counts']['laya_load_completed']==1
        assert v['residency']['cpu_fallback'] is False
        assert v['audit']['first_denial'] is None
        assert v['scratch_cleaned'] is True


def test_hypothesis_requires_real_scratch_file_evidence():
    value={'status':d.PASS,'identities_before':{},'identities_after':{},
        'audit':{'counts':{'allowed_scratch_open_writes':0}},'scratch_inventory':[{'size_bytes':5}]}
    assert not d.supports_guard_hypothesis(value)
    value['audit']['counts']['allowed_scratch_open_writes']=1
    assert d.supports_guard_hypothesis(value)
    value['scratch_inventory']=[]
    assert not d.supports_guard_hypothesis(value)


def test_real_stdlib_tempfile_writes_stay_in_scratch_subprocess(tmp_path):
    import subprocess
    code="""import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,'scripts')
import local_ai_stage_b_laya_base_load_root_cause as d
root=Path(sys.argv[1]);tempfile.tempdir=str(root)
guard=d.Audit(root);sys.addaudithook(guard)
with tempfile.TemporaryDirectory(dir=root) as folder:
    with tempfile.NamedTemporaryFile(dir=folder) as stream:
        stream.write(b'synthetic');stream.flush()
guard.check()
print(json.dumps(guard.summary()))
"""
    result=subprocess.run([str(d.pinned.PYTHON),'-B','-X','utf8','-c',code,str(tmp_path)],
        cwd=d.ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=False)
    assert result.returncode==0,result.stderr.decode('utf-8')
    report=json.loads(result.stdout)
    assert report['first_denial'] is None and report['counts']['allowed_scratch_open_writes']>0


@pytest.mark.parametrize('event',['os.rename','os.link','os.symlink'])
def test_protected_destination_fails(event):
    guard=d.Audit()
    with pytest.raises(PermissionError,match=d.PROTECTED):
        guard(event,(str(d.SCRATCH/'tmp/a'),str(d.pinned.MODEL/'target')))
    assert guard.first_denial['path_category']=='pinned_model'


@pytest.mark.parametrize('target,expected',[(d.pinned.MODEL/'file', 'pinned_model'),(d.SCRATCH.parent/'outside','outside_scratch')])
def test_scratch_alias_cannot_escape(monkeypatch,target,expected):
    alias=d.SCRATCH/'alias/file';original=Path.resolve
    monkeypatch.setattr(Path,'resolve',lambda self,*a,**kw:target if self==alias else original(self,*a,**kw))
    assert d.category(alias)['path_category']==expected
    with pytest.raises(PermissionError):d.Audit()('open',(str(alias),'wb',os.O_WRONLY))


@pytest.mark.parametrize('path',[r'C:\private folder\user file.txt','C:/private folder/user file.txt',str(d.pinned.MODEL/'folder with spaces/file.txt').replace('\\','/')])
def test_sanitizer_spaces_and_forward_slashes(path):
    value=d.sanitized_message("missing '"+path+"'")
    assert path not in value and ':/' not in value and ':\\' not in value
    if 'private folder' in path:assert 'private folder' not in value


@pytest.mark.parametrize('failure',['timeout','missing','exit'])
def test_transport_failure_records_consumed_and_cleans_scratch(monkeypatch,tmp_path,failure):
    import subprocess
    scratch=tmp_path/'guard-regression-v1'
    monkeypatch.setattr(d,'SCRATCH',scratch)
    monkeypatch.setattr(d,'RESULT',tmp_path/'absent.json')
    calls=[]
    def runner(args,**kwargs):
        calls.append((args,kwargs))
        assert kwargs['text'] is False and kwargs['env']['GIT_OPTIONAL_LOCKS']=='0'
        (scratch/'tmp/synthetic.txt').write_text('test',encoding='utf-8')
        if failure=='timeout':raise subprocess.TimeoutExpired(args,300)
        if failure=='missing':return N(stdout=b'no result',stderr=b'',returncode=1)
        value={'status':d.BLOCKER,'scratch_created':True,'execution_counts':{'live_invocations':1,'laya_load_attempts':0},
            'pr86_global_write_guard_regression_supported':False}
        value['canonical_result_sha256']=d.canonical_hash(value)
        return N(stdout=(d.PREFIX+json.dumps(value)).encode(),stderr=b'',returncode=1)
    result=d.parent(runner)
    assert len(calls)==1 and result['status']==d.BLOCKER and result['scratch_cleaned'] is True
    assert result['execution_counts']['live_invocations']==1 and not scratch.exists()
    assert result['scratch_inventory'][0]['size_bytes']==4
    if failure!='exit':assert result['execution_counts']['laya_load_attempts'] is None
    assert result['transport_exception']['stage']=='parent_transport'
