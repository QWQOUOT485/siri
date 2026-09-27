"""Versioned research preflight tests: synthetic dispatch, no model/GPU access."""
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import local_ai_stage_b_laya_s3_research as path


@pytest.fixture
def pr79():
    return path.canonical_evidence('LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json',path.PR79_SHA)


def test_actual_s3_dispatch_masks_and_propagates(monkeypatch):
    calls=[];answer=object()
    def spy(*args):calls.append(args);return answer
    def forbidden(*args,**kwargs):raise AssertionError('historical decoder called')
    monkeypatch.setattr(path.s3_decoder,'decode',spy)
    monkeypatch.setattr(path.historical,'decode',forbidden)
    labels=[-100,1,2,99];mask=[False,True,True,False];offsets=[None,(0,1),(1,3),None]
    result=path.validation_decode(0,.73,labels,mask,offsets,'abc')
    assert result is answer
    assert calls==[(0,.73,[0,1,2,0],mask,offsets,'abc')]
    assert labels==[-100,1,2,99]


def test_mismatched_mask_stops_before_dispatch(monkeypatch):
    monkeypatch.setattr(path.s3_decoder,'decode',lambda *a:pytest.fail('unexpected dispatch'))
    with pytest.raises(ValueError,match=path.BLOCKER):path.validation_decode(0,1,[1],[],[],'x')


def test_real_dispatch_profile_without_global_mutation():
    old=path.historical.decode
    assert path.dispatch_probe()['synthetic_calls']=={'s3':1,'historical':0}
    assert path.historical.decode is old


@pytest.mark.parametrize('addition',[
    '\nhistorical.decode(0,1,[],[],[],"")\n',
    '\nhistorical.decode = s3_decoder.decode\n',
    '\nhistorical.CONFIG = {}\n',
    '\ndef decode(): pass\n',
    '\ndef tighten(): pass\n',
    '\nwhile False: pass\n',
    '\nhistorical.child()\n',
    '\nimport local_ai_stage_b_laya_small_adaptation as old\nold.decode()\n',
    '\nfrom local_ai_stage_b_laya_small_adaptation import decode as old_decode\n'])
def test_ambiguous_or_copied_paths_rejected(addition):
    source=Path(path.__file__).read_text(encoding='utf-8')
    with pytest.raises(ValueError,match=path.AMBIGUOUS):path.source_dispatch_proof(source+addition)


def test_source_has_only_s3_semantic_dependency():
    source=Path(path.__file__).read_text(encoding='utf-8');proof=path.source_dispatch_proof(source)
    assert proof['target']=='s3_decoder.decode'
    forbidden={'load','forward','backward','AdamW','AutoModel','AutoTokenizer','cuda','tensor','mkdir',
               'verified_data','run_validation','child','parent','save_checkpoint','restore_checkpoint'}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node,ast.Call):
            name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
            assert name not in forbidden
        if isinstance(node,ast.Import):assert all(n.name!='torch' for n in node.names)
    assert 'FORBIDDEN_TEXT' not in source
    assert 'sys.addaudithook(no_compute_guard)' in source


def test_recipe_matches_real_config_and_evidence(pr79):
    assert path.recipe_audit(pr79)['all_equal']
    assert set(path.recipe_audit(pr79)['fields'])==set(path.flat(path.RECIPE))


@pytest.mark.parametrize('field',list(path.flat(path.RECIPE)))
def test_every_intended_recipe_field_drift_rejected(field,pr79,monkeypatch):
    changed=copy.deepcopy(path.RECIPE);obj=changed
    parts=field.split('.')
    for key in parts[:-1]:obj=obj[key]
    obj[parts[-1]]='unexpected'
    monkeypatch.setattr(path,'RECIPE',changed)
    with pytest.raises(ValueError,match=path.DRIFT):path.recipe_audit(pr79)


def test_runner_or_evidence_drift_rejected(pr79,monkeypatch):
    changed=copy.deepcopy(pr79);changed['config']['seed']=1730
    with pytest.raises(ValueError,match=path.DRIFT):path.recipe_audit(changed)
    monkeypatch.setitem(path.historical.CONFIG,'seed',1730)
    with pytest.raises(ValueError,match=path.DRIFT):path.recipe_audit(pr79)


def test_source_policy_drift_rejected(pr79,monkeypatch):
    monkeypatch.setattr(path.inspect,'getsource',lambda obj:'')
    with pytest.raises(ValueError,match=path.DRIFT):path.recipe_audit(pr79)


def test_selector_and_schedule_actual_helpers(pr79):
    rows=path.audit.parse_split('train',path.audit.split_path('train').read_bytes())
    selected,manifest=path.historical.select_subset(rows)
    assert manifest==pr79['selection'] and manifest['manifest_sha256']==path.SELECTOR_SHA
    assert len(selected)==600 and len(manifest['eligible_case_ids'])==498
    schedule=path.historical.epoch_batches(manifest['eligible_case_ids'])
    assert schedule==path.historical.epoch_batches(manifest['eligible_case_ids'])
    assert [path.audit.canonical_hash([x for b in e for x in b]) for e in schedule]==pr79['epoch_permutation_sha256']
    assert [list(map(len,e)) for e in schedule]==[[8]*62+[2]]*3


def test_namespace_is_distinct_and_pure(monkeypatch):
    monkeypatch.setattr(Path,'open',lambda *a,**kw:pytest.fail('namespace opened'))
    monkeypatch.setattr(Path,'mkdir',lambda *a,**kw:pytest.fail('namespace created'))
    assert path.checkpoint_identity()['distinct_from_pr79']
    monkeypatch.setattr(path,'FUTURE_CHECKPOINT_NAMESPACE',path.historical.CHECKPOINT_DIR)
    with pytest.raises(ValueError,match='namespace'):path.checkpoint_identity()


def test_exact_repo_main_gate(monkeypatch):
    calls=[]
    def git(args,**kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args,0,stdout=b'wrong\n',stderr=b'')
    monkeypatch.setattr(path.subprocess,'run',git)
    with pytest.raises(ValueError,match='STOP_REVIEWED_STATE_CHANGED'):path.repo_identity()
    assert calls==[['git','rev-parse','origin/main'],['git','merge-base','HEAD',path.BASE]]


def test_historical_source_hashes_and_mutation():
    evidence=path.canonical_evidence('LAYA_SPAN_SEAM_IMPLEMENTATION_RESULT_2026-09-26.json',path.IMPLEMENTATION_SHA)
    assert len(path.historical_hashes(evidence))==6
    evidence['source_hashes']['local_ai_stage_b_laya_span_decoder.py']='wrong'
    with pytest.raises(ValueError,match=path.MUTATED):path.historical_hashes(evidence)


def test_live_cli_is_not_defined():
    env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1');env.pop('PYTHONPATH',None)
    result=subprocess.run([sys.executable,'-B','-X','utf8',path.__file__,'--live'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert result.returncode==2 and b'unrecognized arguments: --live' in result.stderr
    assert not result.stdout


def test_default_cli_only_preflight(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',[path.__file__])
    monkeypatch.setattr(path,'preflight',lambda:{'only':'preflight'})
    assert path.main()==0 and json.loads(capsys.readouterr().out)=={'only':'preflight'}


def test_durable_canonical_record():
    p=path.audit.ROOT/'docs/local_ai/stage_b/evidence/LAYA_S3_RESEARCH_PATH_PREFLIGHT_2026-09-27.json'
    result=json.loads(p.read_bytes());expected=result.pop('canonical_result_sha256')
    assert path.audit.canonical_hash(result)==expected
    assert hashlib.sha256(Path(path.__file__).read_bytes()).hexdigest()==result['research_path_sha256']
    assert result['historical_before']==result['historical_after']
    assert result['selector']['manifest_sha256']==path.SELECTOR_SHA
    assert result['decoder_dispatch']['synthetic_calls']=={'s3':1,'historical':0}
    assert len(result['authority_flags'])==6 and not any(result['authority_flags'].values())
    boundary=result['process_boundary'];assert boundary['opened_corpus_splits']==['train','validation']
    assert boundary['protected_open_attempts']==0 and not boundary['torch_imported']
    for split in path.audit.SPLITS:
        rows=path.audit.parse_split(split,path.audit.split_path(split).read_bytes())
        assert all(r.utterance not in json.dumps(result,ensure_ascii=False) for r in rows)
