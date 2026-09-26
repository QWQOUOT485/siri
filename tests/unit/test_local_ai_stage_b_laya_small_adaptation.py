"""CPU-only tests; toy tensors are separate from the sole live Laya run."""
import copy
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_laya_small_adaptation as s
from test_local_ai_stage_b_laya_training_pipeline_smoke import Tiny, toy_loss


@pytest.fixture(scope="module")
def frozen():
    return s.smoke.parse_train(s.smoke.TRAIN.read_bytes()), s.parse_validation(s.VALIDATION.read_bytes())


def test_exact_train_validation_sha_counts(frozen, monkeypatch):
    assert len(frozen[0]) == 1800 and len(frozen[1]) == 600
    for data, digest, parse in [(s.smoke.TRAIN.read_bytes(), s.smoke.TRAIN_SHA, s.smoke.parse_train),
                                (s.VALIDATION.read_bytes(), s.VALIDATION_SHA, s.parse_validation)]:
        assert hashlib.sha256(data).hexdigest() == digest
        with pytest.raises(s.smoke.DataBoundaryError):
            parse(data + b"x")
    data = b"\n".join(s.VALIDATION.read_bytes().splitlines()[:-1])
    monkeypatch.setattr(s, "VALIDATION_SHA", hashlib.sha256(data).hexdigest())
    with pytest.raises(s.smoke.DataBoundaryError, match="row_count"):
        s.parse_validation(data)


def test_signature_exact_missing_null_and_no_text(frozen):
    rows = frozen[0][:6]
    sig = json.loads(s.group_signature(rows))
    assert len(sig) == 6
    assert set(sig[0]) == {"ai_scope", "expected", "language_tag", "negative_reason", "optional_slot_status"}
    assert sig[0]["expected"] == {"intent": rows[0].expected.intent}
    unknown = [r for r in frozen[0] if r.expected.intent == "unknown"][:6]
    assert json.loads(s.group_signature(unknown))[0]["optional_slot_status"] == {"artist": None, "album": None}
    assert b"utterance" not in s.group_signature(rows)


def test_largest_remainder_exact_oracle_aggregate_and_manifest(frozen):
    rows, manifest = s.select_subset(frozen[0])
    assert len({r.source_group_id for r in frozen[0]}) == 300
    assert manifest["source_group_ids"] == list(s.ORACLE)
    assert (manifest["base_quota_groups"], manifest["remainder_seats"]) == (89, 11)
    assert len(rows) == 600 and len(set(manifest["source_group_ids"])) == 100
    assert len(manifest["eligible_case_ids"]) == 498 and len(manifest["blocked_case_ids"]) == 102
    assert s.select_subset(frozen[0]) == (rows, manifest)
    assert sum(x["quota"] for x in manifest["signature_allocations"]) == 100
    assert manifest["aggregate"]["play_slots"] == {"present/present":138,"present/absent":66,"absent/present":60,"absent/absent":42}
    unsigned = dict(manifest)
    digest = unsigned.pop("manifest_sha256")
    assert s.canonical_hash(unsigned) == digest
    with pytest.raises(s.smoke.DataBoundaryError, match="group_count"):
        s.select_subset(frozen[0][1:])


def test_allocation_tie_order():
    buckets = {bytes([65 + i]): [str(n) for n in range(8)] for i in range(20)}
    with pytest.raises(s.smoke.DataBoundaryError, match=s.SELECTOR):
        s.allocate(buckets)
    # 89 base seats, 12 tied remainder-2 signatures; ascending byte tie break selects first 11.
    buckets = {str(i).zfill(2).encode(): [str(n) for n in range(23 if i < 11 else 38)] for i in range(12)}
    assert sum(len(v)//3 for v in buckets.values()) == 89
    q, base, extra = s.allocate(buckets)
    assert (base, extra) == (89,11)
    assert all(q[k] == len(buckets[k])//3 + (k != b"11") for k in buckets)


def test_oracle_mismatch_stops(frozen, monkeypatch):
    monkeypatch.setattr(s, "ORACLE", tuple(reversed(s.ORACLE)))
    with pytest.raises(s.smoke.DataBoundaryError, match=s.SELECTOR):
        s.select_subset(frozen[0])


def test_three_deterministic_permutations_exact_batches(frozen):
    _, manifest = s.select_subset(frozen[0])
    ids = manifest["eligible_case_ids"]
    epochs = s.epoch_batches(ids)
    assert len(epochs) == 3 and sum(map(len, epochs)) == 189
    for i, batches in enumerate(epochs):
        assert [len(b) for b in batches] == [8]*62 + [2]
        order = list(ids)
        random.Random(1729+i).shuffle(order)
        assert [x for b in batches for x in b] == order
        assert sorted(order) == sorted(ids)
    assert epochs == s.epoch_batches(ids)


def test_train_and_validation_eligibility_before_render(frozen, monkeypatch):
    selected, _ = s.select_subset(frozen[0])
    calls = []
    monkeypatch.setattr(s.adapter, "validate_rendering", lambda tok, build, rows, **kw: calls.extend(rows) or rows)
    for rows, allowed, blocked in [(selected,498,102),(frozen[1],540,60)]:
        eligible = s.eligible_rows(rows, allowed, blocked)
        calls.clear()
        s.render(eligible,None,None,{})
        assert len(calls) == allowed
        for row in rows:
            if row.ai_scope != "supported":
                with pytest.raises(s.pinned.GateError, match=s.LEAK):
                    s.render([row],None,None,{})
        assert len(calls) == allowed


def test_validation_composition_exact(frozen):
    composition = s.validate_validation(frozen[1])
    assert (composition["rows"],composition["groups"],composition["supported"],composition["blocked"]) == (600,100,540,60)
    assert composition["supported_unknown"] == 240 and composition["play"] == 300
    with pytest.raises(s.smoke.DataBoundaryError):
        s.validate_validation(frozen[1][:-1])


def decode(tags, text="abc def ghi", mask=None, offsets=None, typed=0, validity=.5):
    mask = [True]*len(tags) if mask is None else mask
    offsets = [(i, i+1) for i in range(len(tags))] if offsets is None else offsets
    return s.decode(typed,validity,tags,mask,offsets,text)


@pytest.mark.parametrize("tags", [[2,0],[1,1],[1,0,2],[1,2,0,1],[0,0],[3,4]])
def test_invalid_or_multiple_required_track_unknown(tags):
    assert decode(tags)["intent"] == "unknown"


@pytest.mark.parametrize("offsets", [[(-1,1)],[(0,0)],[(0,99)],[(True,1)],[(0,1),(0,1)]])
def test_invalid_offsets_empty_overlap_unknown(offsets):
    assert decode([1]+[2]*(len(offsets)-1),offsets=offsets)["intent"] == "unknown"


def test_empty_span_and_cross_nonuser_unknown():
    assert decode([1],text=" ")["intent"] == "unknown"
    assert decode([1,2],mask=[True,False],offsets=[(0,1),None])["intent"] == "unknown"
    assert decode([1,0,2],mask=[True,False,True],offsets=[(0,1),None,(2,3)])["intent"] == "unknown"


def test_optional_duplicates_or_orphans_null_and_unknown_clears():
    for tags in ([1,0,3,0,3], [1,0,4], [1,0,5,0,5]):
        p = decode(tags)
        assert p["intent"] == "play" and p["artist"] is None and p["album"] is None
    assert decode([1,2],typed=1) == {"intent":"unknown","track":None,"artist":None,"album":None}
    assert decode([1,2],validity=.499999)["intent"] == "unknown"
    assert decode([1,2],validity=.5)["intent"] == "play"
    assert decode([1,2],validity=float("nan"))["intent"] == "unknown"


@pytest.fixture
def tiny():
    model=Tiny()
    span,validity=s.smoke.new_heads(model,"cpu",torch)
    s.training_mode(model,span,validity)
    return model,span,validity


def test_training_eval_policy_optimizer_exact(tiny):
    model,span,validity=tiny
    assert model.training and model.head.training and span.training and validity.training
    assert not model.encoder.training and not model.act_head.training
    optimizer,params=s.make_optimizer(model,span,validity,"cpu",torch)
    groups=s.smoke.parameter_groups(model,span,validity)
    assert {id(p) for p in params} == {id(p) for k in ('typed','span','validity') for p in groups[k].values()}
    assert all(not p.requires_grad for k in ('encoder','act_head') for p in groups[k].values())
    assert s.CONFIG['scheduler'] is None
    for k,v in s.smoke.OPTIMIZER_CONFIG.items(): assert optimizer.param_groups[0][k] == v


def test_189_cpu_updates_clip_order_no_190_final_save_fresh_reload(tiny,tmp_path,monkeypatch):
    torch.set_num_threads(1)
    model,span,validity=tiny
    initial=s.smoke.group_hashes(model,span,validity)
    opt,params=s.make_optimizer(model,span,validity,"cpu",torch)
    events=[]
    clip=torch.nn.utils.clip_grad_norm_
    step=opt.step
    monkeypatch.setattr(torch.nn.utils,"clip_grad_norm_",lambda *a,**k:events.append("clip") or clip(*a,**k))
    monkeypatch.setattr(opt,"step",lambda:events.append("step") or step())
    result={"optimizer_steps":0,"validation_passes":0}
    for _ in range(189):
        opt.zero_grad(set_to_none=True)
        report=s.update_step(result,toy_loss(model,span,validity),model,params,opt,"cpu",torch)
        assert report["finite"] and report["lr"] == 1e-4
    assert events == ["clip","step"]*189
    with pytest.raises(s.pinned.GateError,match="extra_step"):
        s.update_step(result,toy_loss(model,span,validity),model,params,opt,"cpu",torch)
    path=tmp_path/'final.pt'
    binding={"config":json.loads(s.smoke.canonical_bytes(s.CONFIG)),"manifest_sha256":"toy"}
    with pytest.raises(s.pinned.GateError,match="not_final"):
        s.save_checkpoint(path,binding,188,model,span,validity,opt,torch)
    digest=s.save_checkpoint(path,binding,189,model,span,validity,opt,torch)
    payload=torch.load(path,weights_only=True)
    assert set(payload)==s.CHECKPOINT_KEYS
    assert not any(k.startswith(('encoder.','act_head.')) for k in payload['typed'])
    hashes=s.smoke.group_hashes(model,span,validity)
    assert all(hashes[k]==initial[k] for k in ('encoder','act_head'))
    assert all(hashes[k]!=initial[k] for k in ('typed','span','validity'))
    encoder,act_head=model.encoder,model.act_head
    del model,span,validity,opt,params
    model=Tiny(encoder); model.act_head=act_head
    span,validity=s.smoke.new_heads(model,'cpu',torch)
    s.smoke.freeze_policy(model)
    with pytest.raises(s.pinned.GateError,match='binding'):
        s.restore_checkpoint(path,digest,{},model,span,validity,torch)
    s.restore_checkpoint(path,digest,binding,model,span,validity,torch)
    assert s.smoke.group_hashes(model,span,validity)==hashes
    with pytest.raises(s.pinned.GateError,match='sha'):
        s.restore_checkpoint(path,'bad',binding,model,span,validity,torch)


@pytest.mark.parametrize('failure',['loss','gradient','encoder','act_head','feedback'])
def test_fail_closed_before_step(tiny,failure,monkeypatch):
    model,span,validity=tiny
    opt,params=s.make_optimizer(model,span,validity,'cpu',torch)
    calls=[]
    monkeypatch.setattr(opt,'step',lambda:calls.append(1))
    total=toy_loss(model,span,validity)
    if failure=='loss': total=total*float('nan')
    elif failure=='gradient': params[0].register_hook(lambda g:g*float('inf'))
    elif failure in ('encoder','act_head'):
        p=next(getattr(model,failure).parameters());p.grad=torch.ones_like(p)
    with pytest.raises(s.pinned.GateError):
        s.update_step({'optimizer_steps':0,'validation_passes':int(failure=='feedback')},total,model,params,opt,'cpu',torch)
    assert not calls


def test_one_full_validation_metrics_safety_and_no_second(frozen):
    rows=s.eligible_rows(frozen[1],540,60)
    def infer(batch,items):
        return ([{'intent':'unknown','track':None,'artist':None,'album':None} for r in batch],
                [{'typed_play_probability':.2,'validity_probability':.1} for r in batch])
    result={'optimizer_steps':189,'validation_passes':0,'checkpoint':{'reload_verified':True}}
    s.run_validation(result,rows,[{}]*540,infer)
    assert result['validation_passes']==1 and result['status']==s.PASS
    m=result['validation']
    assert m['supported_unknown_recall']==s.rate(240,240)
    assert m['unknown_false_acceptance']==s.rate(0,240)
    assert m['supported_play_recall']==s.rate(0,300)
    assert m['full_semantic_accuracy']==s.rate(240,540)
    assert m['blocked_before_renderer']==s.rate(60,60)
    assert m['predicted_play_without_valid_track']==0 and m['model_rows']==540
    with pytest.raises(s.pinned.GateError,match='validation_order'):
        s.run_validation(result,rows,[{}]*540,infer)
    bad=[{'intent':'play','track':{'start':0,'end':1},'artist':None,'album':None} for r in rows]
    assert s.metrics(rows,bad)['unknown_false_acceptance']==s.rate(240,240)


def test_preexisting_checkpoint_raw_transport_offline_hash(tmp_path,monkeypatch):
    monkeypatch.setattr(s.pinned,'PYTHON',Path(sys.executable))
    directory=tmp_path/'run';directory.mkdir()
    monkeypatch.setattr(s,'CHECKPOINT_DIR',directory)
    with pytest.raises(s.pinned.GateError,match='preexists'):
        s.parent(lambda *a,**k:pytest.fail('child forbidden'))
    assert directory.exists()
    monkeypatch.setattr(s,'CHECKPOINT_DIR',tmp_path/'absent')
    monkeypatch.setenv('PYTHONPATH','testonly')
    payload={'status':s.BLOCK,'blocker':'unit'}
    payload['canonical_result_sha256']=s.canonical_hash(payload)
    def runner(cmd,**kwargs):
        assert cmd[1:4]==['-B','-X','utf8']
        assert kwargs['text'] is False and 'PYTHONPATH' not in kwargs['env']
        assert kwargs['env']['HF_HUB_OFFLINE']==kwargs['env']['TRANSFORMERS_OFFLINE']=='1'
        return subprocess.CompletedProcess(cmd,1,(s.PREFIX+json.dumps(payload)).encode(),b'')
    assert s.parent(runner)==payload
    assert s.canonical_hash({'x':1,'y':[2]})==s.canonical_hash({'y':[2],'x':1})
    with pytest.raises(ValueError):s.canonical_hash({'x':float('nan')})


def test_no_forbidden_model_source_or_validation_optimizer():
    import inspect
    source=inspect.getsource(s.child)
    assert 'load_fixture(' not in source and 'fixture_and_render(' not in source
    validation=inspect.getsource(s.run_validation)
    assert 'optimizer.step' not in validation and 'backward(' not in validation
    assert 'socket.connect' in source and 'socket.getaddrinfo' in source
    with pytest.raises(s.pinned.GateError):s.pinned.require_utf8_mode(0)


def test_shared_mutation_and_device_guards(monkeypatch):
    from local_ai_stage_b_rx9070xt_hardware_preflight import AcceleratorDevice
    target=AcceleratorDevice(3,'AMD Radeon RX 9070 XT','gfx1201',16*1024**3,'cuda')
    assert s.pinned.select_device((target,))=='cuda:3'
    for name in ('model','source','venv','train','validation','seal','corpus','split','selection','provenance'):
        with pytest.raises(s.pinned.GateError,match='changed'):
            s.pinned.require_unchanged({name:'a'},{name:'b'},'changed')


def test_all_eligible_rows_pinned_renderer_mask_bio(frozen):
    import ast
    from test_local_ai_stage_b_laya_head_shape_smoke import CharTokenizer
    common=s.pinned.SOURCE/'laya/common.py'
    if not common.exists():
        pytest.skip('pinned source absent; live child requires it')
    tree=ast.parse(common.read_text(encoding='utf-8'))
    definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
                 ('serialize_state','render_criterion','render_options','build_sequence')]
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*definitions],type_ignores=[])
    namespace={'json':json}
    exec(compile(ast.fix_missing_locations(module),str(common),'exec'),namespace)
    selected,_=s.select_subset(frozen[0])
    for source,eligible_count,blocked_count in [(selected,498,102),(frozen[1],540,60)]:
        rows=s.eligible_rows(source,eligible_count,blocked_count)
        items=s.render(rows,CharTokenizer(),namespace['build_sequence'],{})
        for row,item in zip(rows,items):
            assert all(tag == -100 for tag,mask in zip(item['bio_labels'],item['user_state_mask']) if not mask)
            assert all(item['token_offsets'][i] is None for i,m in enumerate(item['user_state_mask']) if not m)
            if row.expected.intent=='spotify_play_track':assert 1 in item['bio_labels']
            else:assert set(item['bio_labels']) <= {-100,0}
