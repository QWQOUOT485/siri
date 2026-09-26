"""One bounded, offline Laya training-pipeline smoke; no general training authority."""

from __future__ import annotations

import hashlib
import json
import os
import math
import random
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import local_ai_stage_b_corpus as corpus
import local_ai_stage_b_held_out_seal as seal
import local_ai_stage_b_laya_adapter as adapter
import local_ai_stage_b_laya_forward_backward_smoke as shape
import local_ai_stage_b_laya_model_load_preflight as pinned
from local_ai_stage_b_rx9070xt_hardware_preflight import enumerate_accelerators

BASE = "57a07b11f8ae322d39be9379f7423b924880aa0b"
TRAIN = corpus.REPO_ROOT / "artifacts/local_ai/stage_b/final_v1/train.jsonl"
TRAIN_SHA = "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2"
SEAL_SHA = "5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef"
DATA = "STOP_LAYA_TRAINING_PIPELINE_DATA_BOUNDARY"
AUTHORITY_FLAGS = dict.fromkeys(("training_authorized", "model_compute_authorized",
    "semantic_memory_enabled", "local_ai_fallback_approved",
    "LOCAL_SEMANTIC_MEMORY_ENABLED", "LOCAL_AI_FALLBACK_APPROVED"), False)
STRATA = tuple(f"play_artist_{artist}_album_{album}"
               for artist, album in (("present", "present"), ("present", "absent"),
                                     ("absent", "present"), ("absent", "absent"))) + tuple(
    "unknown_" + reason for reason in
    ("missing_track", "artist_only")) + (
    "deterministic_only", "safety_only")
LANGUAGES = ("zh-Hant", "zh-Hans", "mixed")
QUOTAS = {key: dict(zip(LANGUAGES, quotas)) for key, quotas in zip(
    STRATA, ((2, 1, 1), (2, 1, 1), (3, 1, 0), (3, 1, 0),
             (4, 2, 2), (4, 2, 2), (2, 1, 1), (2, 1, 1)))}
ORACLE = tuple("candidate-" + value for value in (
    "00151 00157 00337 00343 00433 00439 00445 00637 00643 00649 "
    "00721 00775 00805 00835 00865 01081 01981 01987 01993 01999 "
    "02005 02011 02017 02023 02281 02287 02293 02299 02437 02443 "
    "02449 02455 03091 03097 03169 03193 03391 03397 03433 03457").split())
ORACLE_STOP = "STOP_LAYA_TRAINING_PIPELINE_SELECTOR_ORACLE_MISMATCH"
LEAK = "STOP_LAYA_TRAINING_PIPELINE_ELIGIBILITY_LEAK"
BLOCK = "LAYA_TRAINING_PIPELINE_NEW_BLOCKER"
PASS = "LAYA_RX9070XT_TRAINING_PIPELINE_SMOKE_PASSED"
RESULT_PREFIX = "STAGE_B_LAYA_TRAINING_RESULT="
CHECKPOINT_DIR = Path(r"D:\ai\ai\stage_b_training_pipeline_smoke\pr76")
VENV_SHA = "3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337"
SEED = 1729
TYPED_PREFIXES = ("type_emb.", "head.", "scorer.")
OPTIMIZER_CONFIG = {"lr": 1e-4, "weight_decay": 0.0, "betas": (0.9, 0.999), "eps": 1e-8,
                    "foreach": False}
CONFIG = {"seed": SEED, "batch_size": 8, "optimizer_steps": 4,
    "optimizer": {"name": "AdamW", **OPTIMIZER_CONFIG},
    "scheduler": {"name": "LambdaLR", "factors": [1.0, .75, .5, .25, 0.0],
                  "order": "optimizer.step then scheduler.step"},
    "clip_max_norm": 1.0, "loss_weights": {"intent": 1, "span": 1, "validity": 1},
    "autocast": "cuda bfloat16", "loss_dtype": "float32", "grad_scaler": False,
    "module_mode": "eval: dropout disabled, allowed parameter gradients enabled",
    "shuffle": False}
CHECKPOINT_KEYS = {"schema", "binding", "completed_steps", "typed", "span", "validity",
                   "optimizer", "scheduler"}


class DataBoundaryError(ValueError):
    """The frozen source cannot satisfy this task's declared subset."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise DataBoundaryError(reason)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_train(data: bytes) -> list[corpus.StageBRecord]:
    require(hashlib.sha256(data).hexdigest() == TRAIN_SHA, "train_byte_sha_mismatch")
    try:
        lines = data.decode("utf-8", "strict").splitlines()
        require(len(lines) == 1800, "train_row_count_mismatch")
        rows = [corpus.StageBRecord.from_mapping(json.loads(line)) for line in lines]
    except DataBoundaryError:
        raise
    except (ValueError, TypeError) as exc:
        raise DataBoundaryError("train_schema_invalid") from exc
    require(len({row.case_id for row in rows}) == 1800, "train_case_ids_not_unique")
    return rows


def verified_data() -> tuple[list[corpus.StageBRecord], dict[str, Any]]:
    # Only TRAIN supplies selectable rows. The existing verifier's broader reads
    # establish integrity only and return no validation/held-out/Stage A rows here.
    rows = parse_train(seal._normal_file(TRAIN, field="train_input"))
    try:
        manifest = seal.verify_seal()
    except (seal.HeldOutSealError, corpus.StageBCorpusError) as exc:
        raise DataBoundaryError("corpus_or_seal_verification_failed") from exc
    require(manifest["seal_manifest_sha256"] == SEAL_SHA
            and manifest["sealed_row_count"] == 600 and manifest["sealed_group_count"] == 100
            and manifest["final_split_assigned"] is True and manifest["held_out_sealed"] is True,
            "seal_identity_mismatch")
    require(all(manifest[key] is False for key in AUTHORITY_FLAGS if key.islower()),
            "persistent_authority_flag_changed")
    require(all(value is False for value in AUTHORITY_FLAGS.values())
            and all(os.environ.get(key, "false").casefold() == "false" for key in AUTHORITY_FLAGS),
            "authority_flag_changed")
    return rows, {"train_sha256": TRAIN_SHA, "train_rows": len(rows),
        "seal_manifest_sha256": manifest["seal_manifest_sha256"],
        "canonical_corpus_sha256": manifest["source_canonical_corpus_sha256"],
        "canonical_split_sha256": manifest["source_canonical_split_sha256"],
        **{key: manifest[key] for key in ("selection_manifest_sha256", "split_assignment_sha256",
                                        "corpus_manifest_sha256", "provenance_manifest_sha256")},
        "split_file_sha256": dict(seal.FROZEN_SPLIT_FILE_SHA256),
        "authoritative_schema_groups_leakage_near_duplicates": "passed"}


def stratum(row: corpus.StageBRecord) -> str | None:
    if row.ai_scope in ("deterministic_only", "safety_only"):
        return row.ai_scope
    if row.ai_scope == "supported" and row.expected.intent == "spotify_play_track":
        return f"play_artist_{row.optional_slot_status['artist']}_album_{row.optional_slot_status['album']}"
    if row.ai_scope == "supported" and row.expected.intent == "unknown":
        return "unknown_" + str(row.negative_reason)
    return None


def select_subset(rows: list[corpus.StageBRecord]) -> tuple[list[corpus.StageBRecord], dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    selected = []
    groups: set[str] = set()
    for row in rows:
        key = stratum(row)
        pair = (key, row.language_tag)
        if (key in QUOTAS and row.source_group_id not in groups
                and counts[pair] < QUOTAS[key].get(row.language_tag, 0)):
            selected.append(row)
            groups.add(row.source_group_id)
            counts[pair] += 1
    expected = {(key, language): quota for key, quotas in QUOTAS.items()
                for language, quota in quotas.items() if quota}
    require(dict(counts) == expected and len(groups) == len(selected) == 40
            and len({row.case_id for row in selected}) == 40, "fixed_quotas_or_unique_groups_invalid")
    eligible = [row.case_id for row in selected if row.ai_scope == "supported"]
    blocked = [row.case_id for row in selected if row.ai_scope != "supported"]
    require(len(eligible) == 32 and len(blocked) == 8, "subset_gate_count_mismatch")
    manifest = {"train_file_sha256": TRAIN_SHA, "selection_algorithm": "canonical-first-unique-group-language-quota-v2",
                "case_ids": [row.case_id for row in selected],
                "source_group_ids": [row.source_group_id for row in selected],
                "per_stratum_counts": dict(Counter(stratum(row) for row in selected)),
                "language_quotas": QUOTAS, "language_counts": dict(Counter(row.language_tag for row in selected)),
                "unique_source_groups": len(groups), "model_eligible_case_ids": eligible,
                "blocked_case_ids": blocked, "source_subset_rows": 40,
                "model_eligible_rows": 32, "blocked_before_model": 8,
                "batches": [eligible[i:i + 8] for i in range(0, 32, 8)]}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    return selected, manifest


def select_frozen_subset(rows: list[corpus.StageBRecord]) -> tuple[list[corpus.StageBRecord], dict[str, Any]]:
    selected, manifest = select_subset(rows)
    require(tuple(manifest["case_ids"]) == ORACLE, ORACLE_STOP)
    require(manifest["language_counts"] == {"zh-Hant": 22, "zh-Hans": 10, "mixed": 8}, "language_total_mismatch")
    require(tuple(manifest["model_eligible_case_ids"]) == ORACLE[:32]
            and tuple(manifest["blocked_case_ids"]) == ORACLE[32:], LEAK)
    return selected, manifest


def preflight() -> dict[str, Any]:
    result: dict[str, Any] = {"schema": "laya-training-pipeline-data-preflight-v1",
        "repo_base": BASE, "status": DATA, "authority_flags": dict(AUTHORITY_FLAGS),
        "live_invocations": 0, "model_loads": 0, "optimizer_steps": 0,
        "checkpoint_created": False}
    before = None
    try:
        rows, before = verified_data()
        result["data_identity_before"] = before
        available = Counter(stratum(row) for row in rows)
        result["available_per_stratum"] = {key: available[key] for key in STRATA}
        result["required_language_quotas"] = QUOTAS
        _, manifest = select_frozen_subset(rows)
        result["subset_manifest"] = manifest
        result["status"] = "DATA_PREFLIGHT_PASSED_NO_MODEL_COMPUTE"
    except DataBoundaryError as exc:
        if str(exc) in (ORACLE_STOP, LEAK):
            result["status"] = str(exc)
        result["blocker"] = str(exc)
    finally:
        if before is not None:
            try:
                _, after = verified_data()
                result["data_identity_after"] = after
                require(before == after, "frozen_data_mutated")
            except DataBoundaryError as exc:
                result.update(status=DATA, blocker=str(exc))
    result["canonical_report_sha256"] = canonical_hash(result)
    return result


def model_row(row: corpus.StageBRecord) -> dict[str, Any]:
    pinned.require(row.ai_scope == "supported", LEAK)
    pinned.require(row.expected.intent in ("spotify_play_track", "unknown"), "bounded_intent_invalid")
    return {"row_id": row.case_id, "utterance": row.utterance, "language": row.language_tag,
        "expected_intent": "play" if row.expected.intent == "spotify_play_track" else "unknown",
        **{name + "_span": None if (span := getattr(row.expected, name)) is None else
           {"start": span.start, "end": span.end} for name in ("track", "artist", "album")}}


def render_eligible(selected: list[corpus.StageBRecord], manifest: dict[str, Any],
                    tok: Any, build_sequence: Any, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    eligible = [row for row in selected if row.ai_scope == "supported"]
    pinned.require([row.case_id for row in eligible] == manifest["model_eligible_case_ids"]
                   and len(eligible) == 32 and len(selected) - len(eligible) == 8, LEAK)
    return adapter.validate_rendering(tok, build_sequence, [model_row(row) for row in eligible],
        max_len=cfg.get("max_len", 512), head_max_len=cfg.get("head_max_len", 192))


def parameter_groups(model: Any, span: Any, validity: Any) -> dict[str, dict[str, Any]]:
    parameters = dict(model.named_parameters())
    pinned.require(all(name.startswith(("encoder.", "act_head.", *TYPED_PREFIXES)) for name in parameters),
                   "unexpected_parameter_group")
    return {"encoder": {n: p for n, p in parameters.items() if n.startswith("encoder.")},
            "act_head": {n: p for n, p in parameters.items() if n.startswith("act_head.")},
            "typed": {n: p for n, p in parameters.items() if n.startswith(TYPED_PREFIXES)},
            "span": dict(span.named_parameters()), "validity": dict(validity.named_parameters())}


def check_frozen(model: Any) -> None:
    for module in (model.encoder, model.act_head):
        pinned.require(all(not p.requires_grad and p.grad is None for p in module.parameters()),
                       "encoder_or_act_head_not_frozen_or_gradient_present")


def freeze_policy(model: Any) -> None:
    for name, parameter in model.named_parameters():
        pinned.require(name.startswith(("encoder.", "act_head.", *TYPED_PREFIXES)), "unexpected_parameter_group")
        parameter.requires_grad_(name.startswith(TYPED_PREFIXES))
    model.eval()  # Disable dropout; eval leaves allowed parameter autograd enabled.
    check_frozen(model)


def state_identity(value: Any) -> Any:
    if hasattr(value, "detach"):
        raw = value.detach().cpu().contiguous().numpy().tobytes()
        return {"dtype": str(value.dtype), "shape": list(value.shape), "sha256": hashlib.sha256(raw).hexdigest()}
    if isinstance(value, dict):
        return {str(key): state_identity(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [state_identity(item) for item in value]
    return value


def state_hash(value: Any) -> str:
    return canonical_hash(state_identity(value))


def group_hashes(model: Any, span: Any, validity: Any) -> dict[str, str]:
    return {name: state_hash(values) for name, values in parameter_groups(model, span, validity).items()}


def new_heads(model: Any, device: str, torch: Any) -> tuple[Any, Any]:
    random.seed(SEED)
    torch.manual_seed(SEED)
    hidden = int(model.encoder.config.hidden_size)
    return torch.nn.Linear(hidden, 7).to(device), torch.nn.Linear(hidden, 1).to(device)


def scheduler_factor(step: int) -> float:
    pinned.require(type(step) is int and 0 <= step <= 4, "scheduler_step_out_of_bounds")
    return CONFIG["scheduler"]["factors"][step]


def optimizer_and_scheduler(model: Any, span: Any, validity: Any, device: str, torch: Any) -> tuple[Any, Any, list[Any]]:
    groups = parameter_groups(model, span, validity)
    check_frozen(model)
    parameters = [p for key in ("typed", "span", "validity") for p in groups[key].values()]
    pinned.require(parameters and len({id(p) for p in parameters}) == len(parameters)
                   and all(p.requires_grad and str(p.device) == device for p in parameters), "optimizer_parameter_policy")
    optimizer = torch.optim.AdamW(parameters, **OPTIMIZER_CONFIG)
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, scheduler_factor)
    return optimizer, scheduler, parameters


def binding_for(manifest: dict[str, Any], identities: dict[str, Any]) -> dict[str, Any]:
    return {"base": BASE, "config": json.loads(canonical_bytes(CONFIG)),
            "subset_manifest_sha256": manifest["manifest_sha256"], "identities": identities}


def save_checkpoint(path: Path, binding: dict[str, Any], completed: int, model: Any,
                    span: Any, validity: Any, optimizer: Any, scheduler: Any, torch: Any) -> str:
    pinned.require(completed == 2 and not path.exists(), "checkpoint_save_requires_step_two_once")
    payload = {"schema": "laya-training-smoke-checkpoint-v1", "binding": binding, "completed_steps": completed,
        "typed": {name: p.detach().clone() for name, p in parameter_groups(model, span, validity)["typed"].items()},
        "span": span.state_dict(), "validity": validity.state_dict(),
        "optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict()}
    with path.open("xb") as stream:
        torch.save(payload, stream)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore_checkpoint(path: Path, digest: str, binding: dict[str, Any], model: Any,
                       span: Any, validity: Any, optimizer: Any, scheduler: Any, torch: Any) -> int:
    pinned.require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "checkpoint_byte_identity_mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    pinned.require(isinstance(payload, dict) and set(payload) == CHECKPOINT_KEYS
                   and payload["schema"] == "laya-training-smoke-checkpoint-v1", "checkpoint_schema_mismatch")
    pinned.require(payload["binding"] == binding, "checkpoint_binding_mismatch")
    pinned.require(type(payload["completed_steps"]) is int and payload["completed_steps"] == 2, "checkpoint_step_mismatch")
    typed = parameter_groups(model, span, validity)["typed"]
    pinned.require(set(payload["typed"]) == set(typed), "checkpoint_parameter_set_mismatch")
    with torch.no_grad():
        for name, parameter in typed.items():
            saved = payload["typed"][name]
            pinned.require(saved.shape == parameter.shape and saved.dtype == parameter.dtype, "checkpoint_tensor_mismatch")
            parameter.copy_(saved)
    span.load_state_dict(payload["span"], strict=True)
    validity.load_state_dict(payload["validity"], strict=True)
    optimizer.load_state_dict(payload["optimizer"])
    scheduler.load_state_dict(payload["scheduler"])
    pinned.require(optimizer.param_groups[0]["lr"] == OPTIMIZER_CONFIG["lr"] * scheduler_factor(2), "checkpoint_next_lr_mismatch")
    return payload["completed_steps"]


def cleanup_checkpoint(directory: Path = CHECKPOINT_DIR) -> None:
    pinned.require(directory.resolve() == CHECKPOINT_DIR.resolve()
                   and not directory.is_symlink() and not getattr(directory, "is_junction", lambda: False)(),
                   "checkpoint_cleanup_path_invalid")
    pinned.require({p.name for p in directory.iterdir()} <= {"step-2.pt"}, "checkpoint_cleanup_unexpected_file")
    shutil.rmtree(directory)
    pinned.require(not directory.exists(), "checkpoint_cleanup_failed")


def require_absent_checkpoint() -> None:
    pinned.require(not CHECKPOINT_DIR.exists() and not CHECKPOINT_DIR.is_symlink(), "checkpoint_directory_preexists")
    for path in CHECKPOINT_DIR.parents:
        pinned.require(not path.is_symlink() and not getattr(path, "is_junction", lambda: False)(), "checkpoint_parent_redirected")


def vram(torch: Any, target: Any) -> dict[str, int]:
    return {"allocated": torch.cuda.memory_allocated(target), "reserved": torch.cuda.memory_reserved(target),
            "peak_allocated": torch.cuda.max_memory_allocated(target), "peak_reserved": torch.cuda.max_memory_reserved(target)}


def update_step(counts: dict[str, int], total: Any, model: Any, parameters: list[Any],
                optimizer: Any, scheduler: Any, device: str, torch: Any) -> dict[str, Any]:
    completed = counts["completed_optimizer_steps"]
    pinned.require(type(completed) is int and 0 <= completed < 4, "fifth_optimizer_step_forbidden")
    shape.require_finite_tensors({"total": total}, device, torch)
    total.backward()
    check_frozen(model)
    pinned.require(all(p.grad is not None for p in parameters), "allowed_gradient_absent")
    before = shape.gradient_norm(parameters, device, torch)
    pinned.require(math.isfinite(before), "aggregate_gradient_nonfinite")
    returned = float(torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True).item())
    after = shape.gradient_norm(parameters, device, torch)
    pinned.require(math.isfinite(returned) and after <= 1.00001, "gradient_clip_failed")
    check_frozen(model)
    lr_before = optimizer.param_groups[0]["lr"]
    pinned.require(lr_before == OPTIMIZER_CONFIG["lr"] * scheduler_factor(completed), "lr_before_mismatch")
    optimizer.step()
    counts["completed_optimizer_steps"] += 1
    scheduler.step()
    for parameter in parameters:
        pinned.require(str(parameter.device) == device and bool(torch.isfinite(parameter).all()), "updated_parameter_invalid")
    for state in optimizer.state.values():
        for key, tensor in state.items():
            if hasattr(tensor, "device"):
                pinned.require(bool(torch.isfinite(tensor).all()) and (key == "step" or str(tensor.device) == device),
                               "optimizer_state_nonfinite_or_wrong_device")
    return {"lr_before": lr_before, "lr_after": optimizer.param_groups[0]["lr"],
            "unclipped_gradient_norm": before, "clip_returned_norm": returned, "clipped_gradient_norm": after,
            "clip_max_norm": 1.0, "gradients_finite": True, "encoder_and_act_head_gradients_absent": True}


def immutable_identity(data: dict[str, Any]) -> dict[str, Any]:
    rows, aggregate = pinned.artifact_inventory()
    pinned.model_identity(rows, aggregate)
    inventory = pinned.package_inventory()
    pinned.require(inventory == VENV_SHA, "venv_inventory_mismatch")
    return {"data": data, "source_revision": pinned.source_identity(), "source_clean": True,
            "model_revision": pinned.MODEL_REVISION, "model_aggregate_sha256": aggregate,
            "primary_weight_sha256": pinned.WEIGHT_SHA, "venv_inventory_sha256": inventory}


def child() -> dict[str, Any]:
    result: dict[str, Any] = {"schema": "laya-training-pipeline-smoke-v2", "status": BLOCK,
        "config": CONFIG, "authority_flags": dict(AUTHORITY_FLAGS), "steps": [],
        "live_invocations": 1, "model_loads": 0, "completed_optimizer_steps": 0,
        "utf8_mode": sys.flags.utf8_mode}
    before = hook = None
    owned_checkpoint_dir = False
    try:
        pinned.require_utf8_mode(sys.flags.utf8_mode)
        require_absent_checkpoint()
        pinned.require(Path(sys.executable).resolve() == pinned.PYTHON.resolve(), "qualified_python_mismatch")
        pinned.require(sys.version_info[:3] == (3, 14, 7), "python_version_mismatch")
        pinned.require(os.environ.get("HF_HUB_OFFLINE") == os.environ.get("TRANSFORMERS_OFFLINE") == "1"
                       and not os.environ.get("PYTHONPATH"), "offline_pristine_process_required")
        from importlib.metadata import version
        for name, expected in pinned.EXPECTED_PACKAGES.items():
            pinned.require(version(name) == expected, "package_version_mismatch")
        def audit(event: str, _args: Any) -> None:
            pinned.require(event not in ("socket.connect", "socket.getaddrinfo"), "network_forbidden")
        sys.addaudithook(audit)
        rows, data = verified_data()
        selected, manifest = select_frozen_subset(rows)
        del rows
        result["subset_manifest"] = manifest
        before = immutable_identity(data)
        result["identities_before"] = before
        import torch
        import torch.nn.functional as F
        from transformers import AutoTokenizer
        pinned.require(torch.__version__ == "2.13.0+rocm10.0.0" and torch.version.hip == "7.15.26333"
                       and torch.version.cuda is None, "rocm_build_mismatch")
        sys.path.insert(0, str(pinned.SOURCE))
        import laya
        from laya.common import build_sequence
        pinned.require(Path(laya.__file__).resolve() == pinned.SOURCE / "laya/__init__.py", "unpinned_laya_import")
        cfg = json.loads((pinned.MODEL / "rl_agent_config.json").read_text(encoding="utf-8"))
        tok = AutoTokenizer.from_pretrained(str(pinned.MODEL / "tokenizer"), local_files_only=True)
        rendered = render_eligible(selected, manifest, tok, build_sequence, cfg)
        result.update(rendering_equivalent_rows=len(rendered), source_subset_rows=40, model_eligible_rows=32, blocked_before_model=8)
        devices = enumerate_accelerators(torch)
        device = pinned.select_device(devices)
        chosen = next(item for item in devices if item.index == int(device[5:]))
        result.update(visible_devices=[vars(item) for item in devices], selected_device=device,
                      selected_gpu=chosen.name, selected_architecture=chosen.architecture)
        target = torch.device(device)
        torch.cuda.set_device(target)
        pinned.require(torch.cuda.current_device() == chosen.index, "current_gpu_not_target")
        torch.cuda.reset_peak_memory_stats(target)
        result["vram"] = {"baseline": vram(torch, target)}
        result.update(pinned.validate_checkpoint_header(pinned.checkpoint_header()))
        started = time.perf_counter()
        result["model_loads"] += 1
        agent = laya.load(str(pinned.MODEL), device=device)
        torch.cuda.synchronize(target)
        result["load_seconds"] = round(time.perf_counter() - started, 6)
        result["residency"] = pinned.residency(agent, device)
        result["vram"]["after_load"] = vram(torch, target)
        model = agent.model
        del agent
        freeze_policy(model)
        span, validity = new_heads(model, device, torch)
        result["parameter_names"] = {key: list(values) for key, values in parameter_groups(model, span, validity).items()}
        result["parameter_hashes_before"] = group_hashes(model, span, validity)
        optimizer, scheduler, parameters = optimizer_and_scheduler(model, span, validity, device, torch)
        binding = binding_for(manifest, before)
        captured: list[Any] = []
        hook = model.encoder.register_forward_hook(lambda _m, _a, out: captured.append(out.last_hidden_state))
        result["vram"]["before_step_1"] = vram(torch, target)
        for index, case_ids in enumerate(manifest["batches"]):
            pinned.require(result["completed_optimizer_steps"] == index, "step_order_mismatch")
            batch_rows = selected[index * 8:(index + 1) * 8]
            pinned.require(len(case_ids) == len(batch_rows) == 8
                           and [row.case_id for row in batch_rows] == case_ids
                           and all(row.ai_scope == "supported" for row in batch_rows)
                           and not set(case_ids) & set(manifest["blocked_case_ids"]), LEAK)
            started = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            captured.clear()
            batch = shape.batch_tensors(rendered[index * 8:(index + 1) * 8], tok.pad_token_id, device, torch)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                typed, action = model(batch["input_ids"], batch["attention_mask"], batch["marker_pos"], batch["marker_mask"], batch["qtype"])
            pinned.require(len(captured) == 1, "encoder_capture_count")
            hidden = captured.pop()
            span_logits = span(hidden.float())
            validity_logits = validity(hidden[:, 0].float()).squeeze(-1)
            outputs = {"typed_logits": typed, "action_logits": action, "hidden_states": hidden,
                "span_logits": span_logits, "validity_logits": validity_logits, "user_state_mask": batch["user_state_mask"]}
            shape.shape_contract({key: tuple(tensor.shape) for key, tensor in outputs.items()})
            shape.require_finite_tensors(outputs, device, torch)
            mask = batch["user_state_mask"]
            pinned.require(bool(mask.any()) and bool((batch["bio_labels"][~mask] == -100).all()), "span_mask_invalid")
            losses = {"intent": F.cross_entropy(typed.float(), batch["intent_label"]),
                "span": F.cross_entropy(span_logits[mask].float(), batch["bio_labels"][mask]),
                "validity": F.binary_cross_entropy_with_logits(validity_logits.float(), batch["validity_label"])}
            losses["total"] = sum(losses.values())
            shape.require_finite_tensors(losses, device, torch)
            update = update_step(result, losses["total"], model, parameters, optimizer, scheduler, device, torch)
            torch.cuda.synchronize(target)
            result["steps"].append({"step": index + 1, "case_ids": case_ids,
                "losses": {key: float(value.item()) for key, value in losses.items()}, **update,
                "selected_gpu": chosen.name, "device": device, "vram": vram(torch, target),
                "elapsed_seconds": round(time.perf_counter() - started, 6)})
            result["vram"][f"after_step_{index + 1}"] = vram(torch, target)
            del outputs, hidden, span_logits, validity_logits, typed, action, losses, batch
            if index == 1:
                require_absent_checkpoint()
                CHECKPOINT_DIR.parent.mkdir(parents=True, exist_ok=True)
                CHECKPOINT_DIR.mkdir(exist_ok=False)
                owned_checkpoint_dir = True
                path = CHECKPOINT_DIR / "step-2.pt"
                hashes = group_hashes(model, span, validity)
                opt_hash, sch_hash = state_hash(optimizer.state_dict()), state_hash(scheduler.state_dict())
                digest = save_checkpoint(path, binding, 2, model, span, validity, optimizer, scheduler, torch)
                result["checkpoint"] = {"path": "<external-smoke-root>/pr76/step-2.pt", "sha256": digest,
                    "saved_completed_steps": 2, "parameter_hashes_step_2": hashes,
                    "optimizer_state_sha256": opt_hash, "scheduler_state_sha256": sch_hash}
                # Reuse frozen modules, but destroy and recreate every trainable module.
                model_type, encoder, act_head, temperature = type(model), model.encoder, model.act_head, model.temperature
                del model, span, validity, optimizer, scheduler, parameters
                torch.manual_seed(SEED)
                model = model_type(encoder, cfg.get("head_layers", 2), len(cfg.get("act_costs", {})) + 1)
                model.act_head, model.temperature = act_head, temperature
                model.to(target)
                freeze_policy(model)
                span, validity = new_heads(model, device, torch)
                optimizer, scheduler, parameters = optimizer_and_scheduler(model, span, validity, device, torch)
                completed = restore_checkpoint(path, digest, binding, model, span, validity, optimizer, scheduler, torch)
                pinned.require(completed == 2 and group_hashes(model, span, validity) == hashes, "checkpoint_parameter_restore_failed")
                pinned.require(state_hash(optimizer.state_dict()) == opt_hash and state_hash(scheduler.state_dict()) == sch_hash,
                               "checkpoint_optimizer_scheduler_restore_failed")
                check_frozen(model)
                result["checkpoint"].update(reload_verified=True, completed_steps_restored=completed,
                    next_lr=optimizer.param_groups[0]["lr"], all_trainable_objects_recreated=True)
                result["vram"]["after_reload"] = vram(torch, target)
        pinned.require(result["completed_optimizer_steps"] == 4, "optimizer_step_count_mismatch")
        check_frozen(model)
        final_hashes = group_hashes(model, span, validity)
        initial = result["parameter_hashes_before"]
        pinned.require(all(final_hashes[key] == initial[key] for key in ("encoder", "act_head")), "frozen_parameters_mutated")
        pinned.require(all(final_hashes[key] != initial[key] for key in ("typed", "span", "validity")), "trainable_parameters_unchanged")
        result["parameter_hashes_after"] = final_hashes
        optimizer.zero_grad(set_to_none=True)
        result["vram"]["final"] = vram(torch, target)
        result["status"] = PASS
    except Exception as exc:
        reason = str(exc) if isinstance(exc, (DataBoundaryError, pinned.GateError, adapter.ShapeError)) else type(exc).__name__
        result.update(status=reason if reason in (ORACLE_STOP, LEAK) else DATA if isinstance(exc, DataBoundaryError) else BLOCK,
                      blocker=reason)
    finally:
        if hook is not None:
            hook.remove()
        if before is not None:
            try:
                _, data_after = verified_data()
                after = immutable_identity(data_after)
                result["identities_after"] = after
                pinned.require(before == after, "source_model_venv_train_manifests_seal_mutated")
            except Exception as exc:
                result.update(status=BLOCK, blocker=str(exc) if isinstance(exc, (DataBoundaryError, pinned.GateError)) else type(exc).__name__)
        if owned_checkpoint_dir:
            try:
                cleanup_checkpoint()
                result.setdefault("checkpoint", {})["cleanup_verified_absent"] = True
            except Exception:
                result.update(status=BLOCK, blocker="checkpoint_cleanup_failed")
    result["canonical_run_summary_sha256"] = canonical_hash(result)
    return result


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    pinned.require(Path(sys.executable).resolve() == pinned.PYTHON.resolve(), "qualified_python_mismatch")
    require_absent_checkpoint()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    completed = runner(pinned.child_command(script=Path(__file__).resolve()), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=False, env=env, timeout=600)
    try:
        matches = [line[len(RESULT_PREFIX):] for line in completed.stdout.decode("utf-8", "strict").splitlines()
                   if line.startswith(RESULT_PREFIX)]
        pinned.require(len(matches) == 1, "child_result_missing_or_ambiguous")
        result = json.loads(matches[0])
        pinned.require(isinstance(result, dict) and isinstance(result.get("status"), str), "child_result_invalid")
        pinned.require((result["status"] == PASS) == (completed.returncode == 0), "child_exit_status_mismatch")
        unsigned = dict(result)
        digest = unsigned.pop("canonical_run_summary_sha256")
        pinned.require(canonical_hash(unsigned) == digest, "child_summary_hash_mismatch")
        return result
    except (UnicodeError, ValueError, KeyError, pinned.GateError):
        return {"status": BLOCK, "blocker": "child_result_unreadable", "child_returncode": completed.returncode}


def main() -> int:
    if sys.argv[1:] == ["--child"]:
        result = child()
        print(RESULT_PREFIX + json.dumps(result, ensure_ascii=True, sort_keys=True))
    elif sys.argv[1:] in ([], ["--preflight"], ["--live"]):
        try:
            result = parent() if sys.argv[1:] == ["--live"] else preflight()
        except Exception as exc:
            result = {"status": BLOCK, "blocker": str(exc) if isinstance(exc, pinned.GateError) else type(exc).__name__}
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    else:
        raise SystemExit("unexpected_arguments")
    return 0 if result["status"] in (PASS, "DATA_PREFLIGHT_PASSED_NO_MODEL_COMPUTE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
