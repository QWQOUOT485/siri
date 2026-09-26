"""Synthetic CPU mechanics and exact frozen selector; never loads Laya model weights."""
import ast
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_laya_training_pipeline_smoke as s
from test_local_ai_stage_b_laya_head_shape_smoke import CharTokenizer


@pytest.fixture
def frozen():
    return s.parse_train(s.TRAIN.read_bytes())


@pytest.fixture
def synthetic():
    rows = []
    for key, quotas in s.QUOTAS.items():
        for language, quota in quotas.items():
            for index in range(quota + 1):
                play = key.startswith("play_")
                artist, album = "artist_present" in key, "album_present" in key
                row = {"case_id": f"unit-{len(rows):03}", "source_group_id": f"unit-group-{len(rows):03}",
                    "utterance": "Tune Artist Album", "language_tag": language,
                    "language_slice": "mixed" if language == "mixed" else "chinese",
                    "ai_scope": "supported" if play or key.startswith("unknown_") else key,
                    "expected": {"intent": "spotify_play_track" if play else "unknown",
                        "track": {"text": "Tune", "start": 0, "end": 4} if play else None,
                        "artist": {"text": "Artist", "start": 5, "end": 11} if artist else None,
                        "album": {"text": "Album", "start": 12, "end": 17} if album else None},
                    "optional_slot_status": {"artist": "present" if artist else "absent",
                        "album": "present" if album else "absent"} if play else None,
                    "negative_reason": None if play else key.removeprefix("unknown_") if key.startswith("unknown_") else
                        "playback_control" if key == "deterministic_only" else "hostile_system",
                    "template_family": "unit", "generator_version": "synthetic-unit-only"}
                rows.append(s.corpus.StageBRecord.from_mapping(row))
    return rows


def test_train_sha_count_and_schema(frozen, monkeypatch):
    assert len(frozen) == 1800
    data = s.TRAIN.read_bytes()
    assert hashlib.sha256(data).hexdigest() == s.TRAIN_SHA
    with pytest.raises(s.DataBoundaryError, match="train_byte_sha"):
        s.parse_train(data + b"\n")
    shortened = b"\n".join(data.splitlines()[:-1])
    monkeypatch.setattr(s, "TRAIN_SHA", hashlib.sha256(shortened).hexdigest())
    with pytest.raises(s.DataBoundaryError, match="train_row_count"):
        s.parse_train(shortened)
    rows = [json.loads(line) for line in data.splitlines()]
    rows[0]["extra"] = "invalid"
    broken = b"\n".join(s.canonical_bytes(row) for row in rows)
    monkeypatch.setattr(s, "TRAIN_SHA", hashlib.sha256(broken).hexdigest())
    with pytest.raises(s.DataBoundaryError, match="train_schema"):
        s.parse_train(broken)


def test_real_frozen_exact_oracle_quotas_groups_languages_batches(frozen):
    rows, manifest = s.select_frozen_subset(frozen)
    assert tuple(manifest["case_ids"]) == s.ORACLE
    assert s.select_frozen_subset(frozen) == (rows, manifest)
    assert len(rows) == len({row.case_id for row in rows}) == len({row.source_group_id for row in rows}) == 40
    assert manifest["language_counts"] == {"zh-Hant": 22, "zh-Hans": 10, "mixed": 8}
    assert list(manifest["per_stratum_counts"].values()).count(8) == 2
    for key, quotas in s.QUOTAS.items():
        for language, quota in quotas.items():
            assert sum(s.stratum(row) == key and row.language_tag == language for row in rows) == quota
    assert manifest["model_eligible_case_ids"] == list(s.ORACLE[:32])
    assert manifest["blocked_case_ids"] == list(s.ORACLE[32:])
    assert manifest["batches"] == [list(s.ORACLE[i:i+8]) for i in range(0, 32, 8)]
    assert (manifest["source_subset_rows"], manifest["model_eligible_rows"], manifest["blocked_before_model"]) == (40,32,8)
    assert manifest["manifest_sha256"] == "790837099986a8b9a4976f83e90f97b423f7d1ac4227976a33b8de8c687c82eb"
    assert sum(row.negative_reason == "artist_only" for row in frozen if row.ai_scope == "supported") == 300
    assert sum(row.negative_reason == "missing_track" for row in frozen if row.ai_scope == "supported") == 300
    assert not any(row.negative_reason in ("unresolved_reference", "ambiguous_version") for row in frozen if row.ai_scope == "supported")


def test_synthetic_first_matching_global_group_and_missing_quota(synthetic):
    chosen, manifest = s.select_subset(synthetic)
    assert len(chosen) == 40
    # Repeated source group cannot be selected twice, even under a new case ID.
    duplicate = chosen[0].to_dict()
    duplicate["case_id"] = "duplicate-variant"
    rows = [synthetic[0], s.corpus.StageBRecord.from_mapping(duplicate), *synthetic[1:]]
    assert s.select_subset(rows)[1]["case_ids"] == manifest["case_ids"]
    with pytest.raises(s.DataBoundaryError, match="fixed_quotas"):
        s.select_subset([row for row in synthetic if row.language_tag != "mixed"])
    with pytest.raises(s.DataBoundaryError, match=s.ORACLE_STOP):
        s.select_frozen_subset(synthetic)
    invalid = synthetic[0].to_dict()
    invalid["expected"]["intent"] = "arbitrary"
    with pytest.raises(s.corpus.StageBCorpusError):
        s.corpus.StageBRecord.from_mapping(invalid)


def test_eligibility_before_renderer_and_manifest_binding(frozen, monkeypatch):
    selected, manifest = s.select_frozen_subset(frozen)
    calls = []
    monkeypatch.setattr(s.adapter, "validate_rendering", lambda tok, build, rows, **kw: calls.extend(rows) or rows)
    s.render_eligible(selected, manifest, None, None, {})
    assert [row["row_id"] for row in calls] == list(s.ORACLE[:32])
    for row in selected[32:]:
        with pytest.raises(s.pinned.GateError, match=s.LEAK):
            s.model_row(row)
    calls.clear()
    changed = copy.deepcopy(manifest)
    changed["model_eligible_case_ids"][0] = s.ORACLE[-1]
    with pytest.raises(s.pinned.GateError, match=s.LEAK):
        s.render_eligible(selected, changed, None, None, {})
    assert calls == []


def test_pinned_renderer_bio_mask_contract_for_32(frozen):
    common = s.pinned.SOURCE / "laya/common.py"
    if not common.exists():
        pytest.skip("pinned local upstream source unavailable; live child requires it")
    assert s.pinned.source_identity() == s.pinned.SOURCE_REVISION
    tree = ast.parse(common.read_text(encoding="utf-8"))
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
        and node.name in ("serialize_state", "render_criterion", "render_options", "build_sequence")]
    namespace = {"json": json}
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *definitions], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(common), "exec"), namespace)
    selected, manifest = s.select_frozen_subset(frozen)
    items = s.render_eligible(selected, manifest, CharTokenizer(), namespace["build_sequence"], {})
    assert len(items) == 32
    for index, item in enumerate(items):
        assert all(label == -100 for label, mask in zip(item["bio_labels"], item["user_state_mask"]) if not mask)
        assert not any(item["user_state_mask"][i] for i in item["marker_pos"])
        assert item["intent_label"] == (0 if index < 16 else 1)
        assert item["validity_label"] == (1 if index < 16 else 0)
        assert 1 in item["bio_labels"] if index < 16 else set(item["bio_labels"]) <= {-100, 0}


class Tiny(torch.nn.Module):
    def __init__(self, encoder=None, head_layers=1, n_act=2):
        super().__init__()
        self.encoder = encoder if encoder is not None else torch.nn.Linear(4, 4)
        self.encoder.config = SimpleNamespace(hidden_size=4)
        self.type_emb = torch.nn.Embedding(3, 4)
        self.head = torch.nn.Linear(4, 4)
        self.scorer = torch.nn.Linear(4, 2)
        self.act_head = torch.nn.Linear(4, n_act)
        self.register_buffer("temperature", torch.ones(3))


@pytest.fixture
def tiny():
    model = Tiny()
    s.freeze_policy(model)
    span, validity = s.new_heads(model, "cpu", torch)
    return model, span, validity


def toy_loss(model, span, validity):
    hidden = model.encoder(torch.ones(8, 4))
    typed = model.scorer(model.head(hidden + model.type_emb(torch.zeros(8, dtype=torch.long))))
    return (torch.nn.functional.cross_entropy(typed, torch.zeros(8, dtype=torch.long))
        + torch.nn.functional.cross_entropy(span(hidden), torch.zeros(8, dtype=torch.long))
        + torch.nn.functional.binary_cross_entropy_with_logits(validity(hidden).squeeze(-1), torch.ones(8)))


def test_frozen_groups_optimizer_exact_config_and_seed(tiny):
    model, span, validity = tiny
    groups = s.parameter_groups(model, span, validity)
    assert all(not p.requires_grad for key in ("encoder", "act_head") for p in groups[key].values())
    optimizer, scheduler, parameters = s.optimizer_and_scheduler(model, span, validity, "cpu", torch)
    assert set(map(id, parameters)) == {id(p) for key in ("typed", "span", "validity") for p in groups[key].values()}
    assert not set(map(id, parameters)) & {id(p) for key in ("encoder", "act_head") for p in groups[key].values()}
    assert s.OPTIMIZER_CONFIG == {"lr": 1e-4, "weight_decay": 0., "betas": (.9,.999), "eps": 1e-8, "foreach": False}
    assert [s.scheduler_factor(i) for i in range(5)] == [1,.75,.5,.25,0]
    for key, value in s.OPTIMIZER_CONFIG.items():
        assert optimizer.param_groups[0][key] == value
    span2, validity2 = s.new_heads(model, "cpu", torch)
    assert s.state_hash(span.state_dict()) == s.state_hash(span2.state_dict())
    assert s.state_hash(validity.state_dict()) == s.state_hash(validity2.state_dict())
    model.unreviewed = torch.nn.Linear(1,1)
    with pytest.raises(s.pinned.GateError, match="unexpected_parameter_group"):
        s.freeze_policy(model)


def test_four_cpu_updates_clipping_step2_recreation_resume_mutation_and_no_fifth(tiny, tmp_path, monkeypatch):
    model, span, validity = tiny
    before = s.group_hashes(model, span, validity)
    optimizer, scheduler, parameters = s.optimizer_and_scheduler(model, span, validity, "cpu", torch)
    counts = {"completed_optimizer_steps": 0}
    events = []
    clip = torch.nn.utils.clip_grad_norm_
    def clip_spy(*args, **kwargs):
        events.append("clip")
        s.check_frozen(model)
        return clip(*args, **kwargs)
    monkeypatch.setattr(torch.nn.utils, "clip_grad_norm_", clip_spy)
    directory = tmp_path / "pr76"
    monkeypatch.setattr(s, "CHECKPOINT_DIR", directory)
    binding = s.binding_for({"manifest_sha256": "synthetic-unit-only"}, {"train": s.TRAIN_SHA})
    path = directory / "step-2.pt"
    for index in range(4):
        optimizer.zero_grad(set_to_none=True)
        old_step = optimizer.step
        def step_spy(*args, **kwargs):
            assert events[-1] == "clip"
            events.append("step")
            return old_step(*args, **kwargs)
        step_spy._wrapped_by_lr_sched = True
        optimizer.step = step_spy
        result = s.update_step(counts, toy_loss(model, span, validity), model, parameters, optimizer, scheduler, "cpu", torch)
        optimizer.step = old_step
        assert result["lr_before"] == 1e-4 * [1,.75,.5,.25][index]
        assert result["lr_after"] == 1e-4 * [.75,.5,.25,0][index]
        assert result["clipped_gradient_norm"] <= 1.00001
        if index == 1:
            directory.mkdir()
            hashes = s.group_hashes(model, span, validity)
            opt_hash, sch_hash = s.state_hash(optimizer.state_dict()), s.state_hash(scheduler.state_dict())
            with pytest.raises(s.pinned.GateError, match="step_two_once"):
                s.save_checkpoint(path,binding,1,model,span,validity,optimizer,scheduler,torch)
            digest = s.save_checkpoint(path,binding,2,model,span,validity,optimizer,scheduler,torch)
            payload = torch.load(path,weights_only=True)
            assert set(payload) == s.CHECKPOINT_KEYS
            assert all(name.startswith(s.TYPED_PREFIXES) for name in payload["typed"])
            encoder, act_head, temperature = model.encoder, model.act_head, model.temperature
            del model, span, validity, optimizer, scheduler, parameters
            model = Tiny(encoder)
            model.act_head, model.temperature = act_head, temperature
            s.freeze_policy(model)
            span, validity = s.new_heads(model,"cpu",torch)
            optimizer,scheduler,parameters = s.optimizer_and_scheduler(model,span,validity,"cpu",torch)
            with pytest.raises(s.pinned.GateError,match="binding_mismatch"):
                s.restore_checkpoint(path,digest,{**binding,"subset_manifest_sha256":"wrong"},model,span,validity,optimizer,scheduler,torch)
            assert s.restore_checkpoint(path,digest,binding,model,span,validity,optimizer,scheduler,torch) == 2
            assert s.group_hashes(model,span,validity) == hashes
            assert s.state_hash(optimizer.state_dict()) == opt_hash
            assert s.state_hash(scheduler.state_dict()) == sch_hash
            assert optimizer.param_groups[0]["lr"] == 5e-5
            with pytest.raises(s.pinned.GateError,match="byte_identity"):
                s.restore_checkpoint(path,"wrong",binding,model,span,validity,optimizer,scheduler,torch)
    assert counts["completed_optimizer_steps"] == 4 and events == ["clip","step"]*4
    with pytest.raises(s.pinned.GateError,match="fifth_optimizer"):
        s.update_step(counts,toy_loss(model,span,validity),model,parameters,optimizer,scheduler,"cpu",torch)
    assert events == ["clip","step"]*4
    after = s.group_hashes(model,span,validity)
    assert all(before[key] == after[key] for key in ("encoder","act_head"))
    assert all(before[key] != after[key] for key in ("typed","span","validity"))
    s.cleanup_checkpoint(directory)
    assert not directory.exists()


@pytest.mark.parametrize("failure", ["loss", "gradient", "encoder", "act_head"])
def test_nonfinite_or_frozen_gradient_stops_before_optimizer(tiny, failure, monkeypatch):
    model,span,validity = tiny
    optimizer,scheduler,parameters = s.optimizer_and_scheduler(model,span,validity,"cpu",torch)
    calls=[]
    monkeypatch.setattr(optimizer,"step",lambda: calls.append(1))
    total=toy_loss(model,span,validity)
    if failure == "loss":
        total=total*float("nan")
    elif failure == "gradient":
        parameters[0].register_hook(lambda grad:grad*float("nan"))
    else:
        p=next(getattr(model,failure).parameters())
        p.grad=torch.ones_like(p)
    counts={"completed_optimizer_steps":0}
    with pytest.raises(s.pinned.GateError):
        s.update_step(counts,total,model,parameters,optimizer,scheduler,"cpu",torch)
    assert not calls and counts["completed_optimizer_steps"] == 0


def test_preexisting_directory_never_deleted_or_child_started(tmp_path,monkeypatch):
    monkeypatch.setattr(s.pinned,"PYTHON",Path(sys.executable))
    directory=tmp_path/"pr76"
    directory.mkdir()
    (directory/"unknown").write_text("preserve")
    monkeypatch.setattr(s,"CHECKPOINT_DIR",directory)
    with pytest.raises(s.pinned.GateError,match="preexists"):
        s.parent(lambda *a,**k:pytest.fail("child must not start"))
    assert (directory/"unknown").read_text() == "preserve"
    with pytest.raises(s.pinned.GateError,match="unexpected_file"):
        s.cleanup_checkpoint(directory)
    assert directory.exists()


def test_raw_byte_transport_utf8_clean_env_and_summary_hash(monkeypatch,tmp_path):
    monkeypatch.setattr(s.pinned,"PYTHON",Path(sys.executable))
    monkeypatch.setattr(s,"CHECKPOINT_DIR",tmp_path/"absent")
    monkeypatch.setenv("PYTHONPATH","untrusted-test-route")
    payload={"status":s.BLOCK,"blocker":"unit"}
    payload["canonical_run_summary_sha256"]=s.canonical_hash(payload)
    def runner(command,**kwargs):
        assert command[1:4] == ["-B","-X","utf8"]
        assert kwargs["text"] is False and "PYTHONPATH" not in kwargs["env"]
        assert kwargs["env"]["HF_HUB_OFFLINE"] == kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"
        return subprocess.CompletedProcess(command,1,(s.RESULT_PREFIX+json.dumps(payload)).encode(),b"invalidutf8:\xff")
    assert s.parent(runner) == payload
    with pytest.raises(s.pinned.GateError,match="utf8_mode_missing"):
        s.pinned.require_utf8_mode(0)
    assert s.canonical_hash({"a":1,"b":2}) == s.canonical_hash({"b":2,"a":1})
    with pytest.raises(ValueError):
        s.canonical_hash({"loss":float("nan")})


@pytest.mark.parametrize("identity",["source","model","venv"])
def test_identity_mutation_fails_closed(identity,monkeypatch):
    monkeypatch.setattr(s.pinned,"artifact_inventory",lambda:([],"aggregate"))
    monkeypatch.setattr(s.pinned,"model_identity",lambda *_:None)
    monkeypatch.setattr(s.pinned,"package_inventory",lambda:s.VENV_SHA)
    monkeypatch.setattr(s.pinned,"source_identity",lambda:s.pinned.SOURCE_REVISION)
    def fail(*args):
        raise s.pinned.GateError(identity+"_mutation")
    monkeypatch.setattr(s.pinned,{"source":"source_identity","model":"model_identity","venv":"package_inventory"}[identity],fail)
    with pytest.raises(s.pinned.GateError,match=identity+"_mutation"):
        s.immutable_identity({})


def test_corpus_seal_failure_stops_selection(monkeypatch):
    monkeypatch.setattr(s.seal,"verify_seal",lambda:(_ for _ in ()).throw(s.seal.HeldOutSealError("test")))
    monkeypatch.setattr(s,"select_frozen_subset",lambda rows:pytest.fail("selection must not run"))
    assert s.preflight()["blocker"] == "corpus_or_seal_verification_failed"


@pytest.mark.parametrize("flag",list(s.AUTHORITY_FLAGS))
def test_authority_flags_false(flag,monkeypatch):
    manifest={"seal_manifest_sha256":s.SEAL_SHA,"sealed_row_count":600,"sealed_group_count":100,
        "final_split_assigned":True,"held_out_sealed":True,**s.AUTHORITY_FLAGS}
    monkeypatch.setattr(s.seal,"verify_seal",lambda:manifest)
    monkeypatch.setenv(flag,"true")
    with pytest.raises(s.DataBoundaryError,match="authority_flag_changed"):
        s.verified_data()


def test_exact_target_and_train_only_input_paths():
    from local_ai_stage_b_rx9070xt_hardware_preflight import AcceleratorDevice, HardwarePreflightError
    target=AcceleratorDevice(2,"AMD Radeon RX 9070 XT","gfx1201",16*1024**3,"cuda")
    igpu=AcceleratorDevice(0,"AMD Radeon(TM) Graphics","gfx1036",1024**3,"cuda")
    assert s.pinned.select_device((igpu,target)) == "cuda:2"
    with pytest.raises(HardwarePreflightError):
        s.pinned.select_device((igpu,))
    with pytest.raises(HardwarePreflightError):
        s.pinned.select_device((target,target))
    with pytest.raises(s.pinned.GateError):
        s.pinned.select_device((target,AcceleratorDevice(1,"NVIDIA RTX 3060","sm86",12*1024**3,"cuda")))
    source=Path(s.__file__).read_text(encoding="utf-8")
    assert 'rows = parse_train(seal._normal_file(TRAIN' in source
    for forbidden in ("validation.jsonl","held_out.jsonl","ai_intent_cases.json","load_fixture(","fixture_and_render("):
        assert forbidden not in source
