"""One research-only Laya adaptation and untouched validation triage; no actions."""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import stat
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import local_ai_stage_b_laya_training_pipeline_smoke as smoke
from local_ai_stage_b_laya_training_pipeline_smoke import adapter, corpus, pinned, seal, shape

BASE = "6219ee24b8e7b75a3ca0a3653774b09ab43ccd5a"
VALIDATION = smoke.TRAIN.with_name("validation.jsonl")
VALIDATION_SHA = "297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a"
CHECKPOINT_DIR = Path(r"D:\ai\ai\stage_b_small_adaptation") / BASE
PASS = "LAYA_RX9070XT_SMALL_ADAPTATION_TRIAGE_PASSED"
SAFETY = "STOP_LAYA_SMALL_ADAPTATION_VALIDATION_SAFETY"
DATA = "STOP_LAYA_SMALL_ADAPTATION_DATA_BOUNDARY"
SELECTOR = "STOP_LAYA_SMALL_ADAPTATION_SELECTOR_MISMATCH"
LEAK = "STOP_LAYA_SMALL_ADAPTATION_ELIGIBILITY_LEAK"
BLOCK = "LAYA_SMALL_ADAPTATION_NEW_BLOCKER"
PREFIX = "STAGE_B_LAYA_SMALL_ADAPTATION_RESULT="
ORACLE = tuple("source-group-" + x for x in (
    "0026 0027 0028 0029 0030 0031 0032 0033 0057 0058 0059 0060 0061 "
    "0073 0074 0075 0076 0077 0078 0079 0080 0107 0108 0109 0110 0111 "
    "0121 0122 0123 0130 0131 0135 0136 0140 0141 0145 0146 0147 0148 "
    "0149 0150 0151 0152 0153 0154 0155 0156 0181 0182 0183 0184 "
    "0331 0332 0333 0334 0335 0336 0337 0338 0339 0340 0341 0342 0343 "
    "0344 0345 0346 0381 0382 0383 0384 0407 0408 0409 0410 0411 0412 "
    "0413 0414 0415 0416 0417 0418 0516 0517 0522 0525 0527 0529 0533 "
    "0534 0535 0536 0544 0566 0567 0573 0577 0578 0579").split())
CONFIG = {"seed": 1729, "epochs": 3, "batch_size": 8, "drop_last": False,
    "steps_per_epoch": 63, "optimizer_steps": 189, "validation_batch_size": 16,
    "optimizer": {"name": "AdamW", **smoke.OPTIMIZER_CONFIG}, "scheduler": None,
    "clip_max_norm": 1.0, "validity_threshold": 0.5,
    "loss_weights": {"intent": 1.0, "span": 1.0, "validity": 1.0},
    "autocast": "cuda bfloat16", "loss_metric_dtype": "float32", "grad_scaler": False,
    "training_mode": "trainable modules train; encoder and act_head eval",
    "decoder": "strict-grounded-bio-v1", "validation_passes": 1}
canonical_hash = smoke.canonical_hash
require = pinned.require


def parse_validation(data: bytes) -> list[Any]:
    smoke.require(hashlib.sha256(data).hexdigest() == VALIDATION_SHA, "validation_sha_mismatch")
    lines = data.decode("utf-8", "strict").splitlines()
    smoke.require(len(lines) == 600, "validation_row_count_mismatch")
    rows = [corpus.StageBRecord.from_mapping(json.loads(line)) for line in lines]
    smoke.require(len({r.case_id for r in rows}) == 600, "validation_duplicate_id")
    return rows


def verified_data() -> tuple[list[Any], list[Any], dict[str, Any]]:
    train, identity = smoke.verified_data()
    validation = parse_validation(seal._normal_file(VALIDATION, field="validation_input"))
    identity = {**identity, "validation_sha256": VALIDATION_SHA, "validation_rows": 600}
    validate_validation(validation)
    return train, validation, identity


def group_signature(rows: list[Any]) -> bytes:
    return smoke.canonical_bytes([{"ai_scope": r.ai_scope, "expected": {"intent": r.expected.intent},
        "language_tag": r.language_tag, "negative_reason": r.negative_reason,
        "optional_slot_status": {k: (r.optional_slot_status or {}).get(k) for k in ("artist", "album")}}
        for r in rows])


def allocate(buckets: dict[bytes, list[str]]) -> tuple[dict[bytes, int], int, int]:
    quotas = {signature: len(groups) // 3 for signature, groups in buckets.items()}
    base = sum(quotas.values())
    extra = 100 - base
    smoke.require(base == 89 and extra == 11, SELECTOR)
    for signature in sorted(buckets, key=lambda x: (-(len(buckets[x]) % 3), x))[:extra]:
        quotas[signature] += 1
    return quotas, base, extra


def aggregates(rows: list[Any]) -> dict[str, Any]:
    return {"rows": len(rows), "groups": len({r.source_group_id for r in rows}),
        "scope": dict(Counter(r.ai_scope for r in rows)),
        "language": dict(Counter(r.language_tag for r in rows)),
        "intent": dict(Counter(r.expected.intent for r in rows)),
        "supported_unknown": dict(Counter(r.negative_reason for r in rows
            if r.ai_scope == "supported" and r.expected.intent == "unknown")),
        "play_slots": dict(Counter("/".join(r.optional_slot_status[k] for k in ("artist", "album"))
            for r in rows if r.expected.intent == "spotify_play_track"))}


def select_subset(rows: list[Any]) -> tuple[list[Any], dict[str, Any]]:
    groups: dict[str, list[Any]] = {}
    for row in rows:
        groups.setdefault(row.source_group_id, []).append(row)
    smoke.require(len(rows) == 1800 and len(groups) == 300
                  and all(len(v) == 6 for v in groups.values()), "train_group_count_or_size")
    buckets: dict[bytes, list[str]] = {}
    for gid, group in groups.items():
        buckets.setdefault(group_signature(group), []).append(gid)
    quotas, base, extra = allocate(buckets)
    chosen = {gid for sig, ids in buckets.items() for gid in ids[:quotas[sig]]}
    ordered = [gid for gid in groups if gid in chosen]
    smoke.require(tuple(ordered) == ORACLE, SELECTOR)
    selected = [row for row in rows if row.source_group_id in chosen]
    counts = aggregates(selected)
    smoke.require(counts == {"rows": 600, "groups": 100,
        "scope": {"supported": 498, "deterministic_only": 66, "safety_only": 36},
        "language": {"zh-Hant": 294, "zh-Hans": 90, "mixed": 216},
        "intent": {"spotify_play_track": 306, "unknown": 294},
        "supported_unknown": {"artist_only": 96, "missing_track": 96},
        "play_slots": {"present/present": 138, "present/absent": 66,
                       "absent/present": 60, "absent/absent": 42}}, "selected_aggregate_mismatch")
    manifest = {"algorithm": "six-row-signature-largest-remainder-third-v1", "train_sha256": smoke.TRAIN_SHA,
        "source_group_ids": ordered, "base_quota_groups": base, "remainder_seats": extra,
        "signature_allocations": [{"signature_sha256": hashlib.sha256(sig).hexdigest(),
            "available": len(buckets[sig]), "quota": quotas[sig]} for sig in sorted(buckets)],
        "aggregate": counts, "case_ids": [r.case_id for r in selected],
        "eligible_case_ids": [r.case_id for r in selected if r.ai_scope == "supported"],
        "blocked_case_ids": [r.case_id for r in selected if r.ai_scope != "supported"]}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    return selected, manifest


def validate_validation(rows: list[Any]) -> dict[str, Any]:
    smoke.require(len(rows) == 600 and len({r.source_group_id for r in rows}) == 100
        and all(n == 6 for n in Counter(r.source_group_id for r in rows).values()), "validation_group_count")
    counts = Counter((r.ai_scope, r.expected.intent, r.language_tag, r.negative_reason) for r in rows)
    expected = {("supported", "spotify_play_track", "mixed", None): 204,
        ("supported", "spotify_play_track", "en", None): 96,
        ("supported", "unknown", "mixed", "artist_only"): 78,
        ("supported", "unknown", "mixed", "missing_track"): 78,
        ("supported", "unknown", "en", "artist_only"): 42,
        ("supported", "unknown", "en", "missing_track"): 42,
        ("deterministic_only", "unknown", "mixed", "ambiguous_version"): 18,
        ("deterministic_only", "unknown", "mixed", "unsupported_domain"): 12,
        ("safety_only", "unknown", "mixed", "hostile_system"): 12,
        ("safety_only", "unknown", "mixed", "path_or_url"): 6,
        ("safety_only", "unknown", "en", "hostile_system"): 8,
        ("safety_only", "unknown", "en", "path_or_url"): 4}
    smoke.require(dict(counts) == expected, "validation_composition_mismatch")
    return {"rows": 600, "groups": 100, "supported": 540, "play": 300,
        "supported_unknown": 240, "blocked": 60,
        "composition": [{"scope": k[0], "intent": k[1], "language": k[2], "reason": k[3], "rows": v}
                        for k, v in expected.items()]}


def epoch_batches(ids: list[str]) -> list[list[list[str]]]:
    require(len(ids) == len(set(ids)) == 498, "eligible_id_count")
    epochs = []
    for epoch in range(3):
        order = list(ids)
        random.Random(1729 + epoch).shuffle(order)
        batches = [order[i:i + 8] for i in range(0, len(order), 8)]
        require(len(batches) == 63 and [len(b) for b in batches] == [8] * 62 + [2], "epoch_batch_shape")
        epochs.append(batches)
    return epochs


def eligible_rows(rows: list[Any], eligible_count: int, blocked_count: int) -> list[Any]:
    eligible = [r for r in rows if r.ai_scope == "supported"]
    require(len(eligible) == eligible_count and len(rows) - len(eligible) == blocked_count, LEAK)
    return eligible


def render(rows: list[Any], tok: Any, build_sequence: Any, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    require(all(r.ai_scope == "supported" for r in rows), LEAK)
    return adapter.validate_rendering(tok, build_sequence, [smoke.model_row(r) for r in rows],
        max_len=cfg.get("max_len", 512), head_max_len=cfg.get("head_max_len", 192))


def decode(typed_index: int, validity_probability: float, labels: list[int],
           mask: list[bool], offsets: list[Any], utterance: str) -> dict[str, Any]:
    """Strict BIO decoding into raw offsets only; never an execution target."""
    null = {"intent": "unknown", "track": None, "artist": None, "album": None}
    if typed_index not in (0, 1) or not math.isfinite(validity_probability) or not 0 <= validity_probability <= 1:
        return null
    if typed_index != 0 or validity_probability < 0.5:
        return null
    if len(labels) != len(mask) or len(mask) != len(offsets):
        return null
    spans: dict[str, list[tuple[int, int]]] = {k: [] for k in ("track", "artist", "album")}
    bad: set[str] = set()
    active = None
    last_end = -1
    for i, tag in enumerate(labels):
        if type(tag) is not int or tag not in range(7):
            return null
        if not mask[i]:
            if tag != 0 or offsets[i] is not None:
                return null
            active = None
            continue
        pair = offsets[i]
        if (not isinstance(pair, (tuple, list)) or len(pair) != 2
                or any(type(v) is not int for v in pair)
                or not 0 <= pair[0] < pair[1] <= len(utterance) or pair[0] < last_end):
            return null
        last_end = pair[1]
        if tag == 0:
            active = None
            continue
        name = ("track", "artist", "album")[(tag - 1) // 2]
        if tag % 2:
            spans[name].append((pair[0], pair[1]))
            active = name
        elif active != name:
            bad.add(name)
            active = None
        else:
            a, _ = spans[name][-1]
            spans[name][-1] = (a, pair[1])
    grounded = {}
    for name, values in spans.items():
        value = values[0] if len(values) == 1 and name not in bad else None
        if value is not None:
            text = utterance[value[0]:value[1]]
            if not text.strip() or adapter.FORBIDDEN_TEXT.search(text):
                value = None
        grounded[name] = None if value is None else {"start": value[0], "end": value[1]}
    return {"intent": "play", **grounded} if grounded["track"] is not None else null


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {"numerator": numerator, "denominator": denominator,
            "rate": numerator / denominator if denominator else None}


def metrics(rows: list[Any], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    require(len(rows) == len(predictions) and all(r.ai_scope == "supported" for r in rows), LEAK)
    play = [(r, p) for r, p in zip(rows, predictions) if r.expected.intent == "spotify_play_track"]
    unknown = [(r, p) for r, p in zip(rows, predictions) if r.expected.intent == "unknown"]
    def exact(r: Any, p: dict[str, Any], slot: str) -> bool:
        target = getattr(r.expected, slot)
        return p[slot] == (None if target is None else {"start": target.start, "end": target.end})
    semantic = sum(p["intent"] == ("play" if r.expected.intent == "spotify_play_track" else "unknown")
                   and all(exact(r, p, s) for s in ("track", "artist", "album")) for r, p in zip(rows, predictions))
    result = {"supported_unknown_recall": rate(sum(p["intent"] == "unknown" for _, p in unknown), len(unknown)),
        "unknown_false_acceptance": rate(sum(p["intent"] == "play" for _, p in unknown), len(unknown)),
        "supported_play_recall": rate(sum(p["intent"] == "play" for _, p in play), len(play)),
        "full_semantic_accuracy": rate(semantic, len(rows)),
        "predicted_play_without_valid_track": sum(p["intent"] == "play" and p["track"] is None for p in predictions)}
    for slot in ("track", "artist", "album"):
        present = [(r, p) for r, p in play if getattr(r.expected, slot) is not None]
        absent = [(r, p) for r, p in play if getattr(r.expected, slot) is None]
        result[slot] = {"presence_recall": rate(sum(p[slot] is not None for _, p in present), len(present)),
            "exact_span": rate(sum(exact(r, p, slot) for r, p in present), len(present)),
            "correct_null": rate(sum(p[slot] is None for _, p in absent), len(absent))}
    return result


def training_mode(model: Any, span: Any, validity: Any) -> None:
    smoke.freeze_policy(model)
    model.train()
    model.encoder.eval()
    model.act_head.eval()
    span.train()
    validity.train()
    require(model.training and not model.encoder.training and not model.act_head.training
            and span.training and validity.training, "module_mode_mismatch")


def make_optimizer(model: Any, span: Any, validity: Any, device: str, torch: Any) -> tuple[Any, list[Any]]:
    smoke.check_frozen(model)
    groups = smoke.parameter_groups(model, span, validity)
    parameters = [p for k in ("typed", "span", "validity") for p in groups[k].values()]
    require(len(parameters) == len({id(p) for p in parameters}) and all(p.requires_grad
            and str(p.device) == device for p in parameters), "optimizer_parameter_set")
    return torch.optim.AdamW(parameters, **smoke.OPTIMIZER_CONFIG), parameters


def update_step(counts: dict[str, Any], total: Any, model: Any, parameters: list[Any],
                optimizer: Any, device: str, torch: Any) -> dict[str, Any]:
    require(type(counts["optimizer_steps"]) is int and 0 <= counts["optimizer_steps"] < 189
            and counts.get("validation_passes", 0) == 0, "extra_step_or_validation_feedback")
    shape.require_finite_tensors({"total": total}, device, torch)
    total.backward()
    smoke.check_frozen(model)
    require(all(p.grad is not None for p in parameters), "allowed_gradient_absent")
    norm = shape.gradient_norm(parameters, device, torch)
    returned = float(torch.nn.utils.clip_grad_norm_(parameters, 1.0, error_if_nonfinite=True).item())
    clipped = shape.gradient_norm(parameters, device, torch)
    require(math.isfinite(norm) and math.isfinite(returned) and clipped <= 1.00001, "gradient_clip_invalid")
    smoke.check_frozen(model)
    require(all(g["lr"] == 1e-4 for g in optimizer.param_groups), "constant_lr_changed")
    optimizer.step()
    counts["optimizer_steps"] += 1
    require(all(str(p.device) == device and bool(torch.isfinite(p).all()) for p in parameters), "updated_parameter_invalid")
    for state in optimizer.state.values():
        for name, value in state.items():
            if hasattr(value, "device"):
                require(bool(torch.isfinite(value).all()) and (name == "step" or str(value.device) == device), "optimizer_state_invalid")
    return {"unclipped_norm": norm, "clip_returned_norm": returned, "clipped_norm": clipped,
            "lr": 1e-4, "finite": True, "frozen_gradients_absent": True}


def require_absent_checkpoint() -> None:
    require(not CHECKPOINT_DIR.exists() and not CHECKPOINT_DIR.is_symlink(), "checkpoint_directory_preexists")
    for path in (CHECKPOINT_DIR, *CHECKPOINT_DIR.parents):
        require(not path.is_symlink() and not getattr(path, "is_junction", lambda: False)(), "checkpoint_path_redirected")


CHECKPOINT_KEYS = {"schema", "typed", "span", "validity", "optimizer", "completed_steps", "binding"}


def save_checkpoint(path: Path, binding: dict[str, Any], completed: int, model: Any,
                    span: Any, validity: Any, optimizer: Any, torch: Any) -> str:
    require(completed == 189, "checkpoint_not_final")
    payload = {"schema": "laya-small-adaptation-final-v1", "binding": binding, "completed_steps": completed,
        "typed": {n: p.detach().clone() for n, p in smoke.parameter_groups(model, span, validity)["typed"].items()},
        "span": span.state_dict(), "validity": validity.state_dict(), "optimizer": optimizer.state_dict()}
    with path.open("xb") as stream:
        torch.save(payload, stream)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def restore_checkpoint(path: Path, digest: str, binding: dict[str, Any], model: Any,
                       span: Any, validity: Any, torch: Any) -> None:
    require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, "checkpoint_sha_mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    require(isinstance(payload, dict) and set(payload) == CHECKPOINT_KEYS
            and payload["schema"] == "laya-small-adaptation-final-v1", "checkpoint_schema")
    require(payload["binding"] == binding and payload["completed_steps"] == 189, "checkpoint_binding_or_step")
    typed = smoke.parameter_groups(model, span, validity)["typed"]
    require(set(payload["typed"]) == set(typed), "checkpoint_parameter_set")
    with torch.no_grad():
        for name, p in typed.items():
            saved = payload["typed"][name]
            require(p.shape == saved.shape and p.dtype == saved.dtype, "checkpoint_tensor_identity")
            p.copy_(saved)
    span.load_state_dict(payload["span"], strict=True)
    validity.load_state_dict(payload["validity"], strict=True)


def preflight() -> dict[str, Any]:
    train, validation, identity = verified_data()
    _, manifest = select_subset(train)
    epochs = epoch_batches(manifest["eligible_case_ids"])
    return {"status": "DATA_PREFLIGHT_PASSED_NO_MODEL_COMPUTE", "identity": identity,
        "selection": manifest, "validation": validate_validation(validation),
        "epoch_permutation_sha256": [canonical_hash([x for b in e for x in b]) for e in epochs]}


def forward(model: Any, span: Any, validity: Any, items: list[dict[str, Any]],
            pad_id: int, device: str, captured: list[Any], torch: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    captured.clear()
    batch = shape.batch_tensors(items, pad_id, device, torch)
    with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
        typed, action = model(batch["input_ids"], batch["attention_mask"], batch["marker_pos"], batch["marker_mask"], batch["qtype"])
    require(len(captured) == 1, "encoder_capture_count")
    hidden = captured.pop()
    outputs = {"typed_logits": typed, "action_logits": action, "hidden_states": hidden,
        "span_logits": span(hidden.float()), "validity_logits": validity(hidden[:, 0].float()).squeeze(-1),
        "user_state_mask": batch["user_state_mask"]}
    shape.shape_contract({k: tuple(v.shape) for k, v in outputs.items()}, batch=len(items))
    shape.require_finite_tensors(outputs, device, torch)
    return batch, outputs


def begin_validation(result: dict[str, Any]) -> None:
    require(result["optimizer_steps"] == 189 and result["validation_passes"] == 0
            and result["checkpoint"]["reload_verified"] is True, "validation_order_or_repeat")
    result["validation_passes"] += 1


def run_validation(result: dict[str, Any], rows: list[Any], items: list[dict[str, Any]],
                   infer: Any) -> None:
    """One pass, no optimizer access. infer returns decoded proposals and confidences."""
    begin_validation(result)
    require(len(rows) == len(items) == 540 and len({r.case_id for r in rows}) == 540
            and all(r.ai_scope == "supported" for r in rows), LEAK)
    predictions, confidence, seen = [], [], []
    for start in range(0, 540, 16):
        batch_rows = rows[start:start + 16]
        proposals, probabilities = infer(batch_rows, items[start:start + 16])
        require(len(proposals) == len(probabilities) == len(batch_rows), "validation_batch_count")
        predictions.extend(proposals)
        confidence.extend(probabilities)
        seen.extend(r.case_id for r in batch_rows)
    require(seen == [r.case_id for r in rows], "validation_coverage")
    report = metrics(rows, predictions)
    require(report["supported_unknown_recall"]["denominator"] == 240
            and report["supported_play_recall"]["denominator"] == 300, "validation_denominator")
    report["blocked_before_renderer"] = rate(60, 60)
    report["eligibility_leakage"] = 0
    report["model_rows"] = 540
    report["case_ids"] = seen
    report["slices"] = {language: metrics([r for r in rows if r.language_tag == language],
        [p for r, p in zip(rows, predictions) if r.language_tag == language]) for language in ("mixed", "en")}
    report["uncalibrated_confidence"] = {}
    for expected in ("spotify_play_track", "unknown"):
        values = [c for r, c in zip(rows, confidence) if r.expected.intent == expected]
        report["uncalibrated_confidence"][expected] = {key: {"min": min(c[key] for c in values),
            "max": max(c[key] for c in values), "mean": sum(c[key] for c in values) / len(values)}
            for key in ("typed_play_probability", "validity_probability")}
    report["predictions"] = [{"case_id": r.case_id, **p} for r, p in zip(rows, predictions)]
    report["safety_triage_passed"] = (report["supported_unknown_recall"]["numerator"] == 240
        and report["unknown_false_acceptance"]["numerator"] == 0
        and report["eligibility_leakage"] == 0 and report["predicted_play_without_valid_track"] == 0)
    result["validation"] = report
    result["status"] = PASS if report["safety_triage_passed"] else SAFETY


def child() -> dict[str, Any]:
    result: dict[str, Any] = {"schema": "laya-small-adaptation-v1", "status": BLOCK,
        "repo_base": BASE, "config": CONFIG, "authority_flags": dict(smoke.AUTHORITY_FLAGS),
        "live_invocations": 1, "model_loads": 0, "optimizer_steps": 0, "validation_passes": 0,
        "steps": [], "epochs": [], "utf8_mode": sys.flags.utf8_mode}
    before = hook = path = None
    try:
        pinned.require_utf8_mode(sys.flags.utf8_mode)
        require_absent_checkpoint()
        require(Path(sys.executable).resolve() == pinned.PYTHON.resolve()
                and sys.version_info[:3] == (3, 14, 7), "qualified_python_mismatch")
        require(os.environ.get("HF_HUB_OFFLINE") == os.environ.get("TRANSFORMERS_OFFLINE") == "1"
                and not os.environ.get("PYTHONPATH"), "offline_pristine_process_required")
        def audit(event: str, _args: Any) -> None:
            require(event not in ("socket.connect", "socket.getaddrinfo"), "network_forbidden")
        sys.addaudithook(audit)
        from importlib.metadata import version
        for name, expected in pinned.EXPECTED_PACKAGES.items():
            require(version(name) == expected, "package_version_mismatch")
        train, validation_rows, data = verified_data()
        selected, manifest = select_subset(train)
        del train
        train_rows = eligible_rows(selected, 498, 102)
        val_rows = eligible_rows(validation_rows, 540, 60)
        result.update(selection=manifest, validation_composition=validate_validation(validation_rows),
            blocked_validation_case_ids=[r.case_id for r in validation_rows if r.ai_scope != "supported"])
        before = smoke.immutable_identity(data)
        result["identities_before"] = before
        import torch
        import torch.nn.functional as F
        from transformers import AutoTokenizer
        require(torch.__version__ == "2.13.0+rocm10.0.0" and torch.version.hip == "7.15.26333"
                and torch.version.cuda is None, "rocm_build_mismatch")
        random.seed(1729)
        torch.manual_seed(1729)
        torch.cuda.manual_seed_all(1729)
        sys.path.insert(0, str(pinned.SOURCE))
        import laya
        from laya.common import build_sequence
        require(Path(laya.__file__).resolve() == pinned.SOURCE / "laya/__init__.py", "unpinned_laya_import")
        cfg = json.loads((pinned.MODEL / "rl_agent_config.json").read_text(encoding="utf-8"))
        tok = AutoTokenizer.from_pretrained(str(pinned.MODEL / "tokenizer"), local_files_only=True)
        train_rendered = render(train_rows, tok, build_sequence, cfg)
        val_rendered = render(val_rows, tok, build_sequence, cfg)
        result["rendering_equivalence"] = {"train": len(train_rendered), "validation": len(val_rendered)}
        epochs = epoch_batches(manifest["eligible_case_ids"])
        result["epoch_permutation_sha256"] = [canonical_hash([x for b in e for x in b]) for e in epochs]
        by_id = dict(zip(manifest["eligible_case_ids"], train_rendered))
        devices = smoke.enumerate_accelerators(torch)
        device = pinned.select_device(devices)
        chosen = next(d for d in devices if d.index == int(device[5:]))
        result.update(visible_devices=[vars(d) for d in devices], selected_device=device,
                      selected_gpu=chosen.name, selected_architecture=chosen.architecture)
        target = torch.device(device)
        torch.cuda.set_device(target)
        require(torch.cuda.current_device() == chosen.index, "current_gpu_mismatch")
        torch.cuda.reset_peak_memory_stats(target)
        result["vram"] = {"baseline": smoke.vram(torch, target)}
        result.update(pinned.validate_checkpoint_header(pinned.checkpoint_header()))
        started = time.perf_counter()
        result["model_loads"] += 1
        agent = laya.load(str(pinned.MODEL), device=device)
        torch.cuda.synchronize(target)
        result["load_seconds"] = time.perf_counter() - started
        result["residency"] = pinned.residency(agent, device)
        result["vram"]["after_load"] = smoke.vram(torch, target)
        model = agent.model
        del agent
        span, validity = smoke.new_heads(model, device, torch)
        training_mode(model, span, validity)
        result["parameter_hashes_before"] = smoke.group_hashes(model, span, validity)
        result["parameter_names"] = {k: list(v) for k, v in smoke.parameter_groups(model, span, validity).items()}
        optimizer, parameters = make_optimizer(model, span, validity, device, torch)
        captured: list[Any] = []
        hook = model.encoder.register_forward_hook(lambda _m, _a, out: captured.append(out.last_hidden_state))
        train_started = time.perf_counter()
        for epoch, batches in enumerate(epochs):
            epoch_started = time.perf_counter()
            torch.cuda.reset_peak_memory_stats(target)
            sums = {k: torch.zeros((), dtype=torch.float32, device=device) for k in ("intent", "span", "validity", "total")}
            for ids in batches:
                require(not set(ids) & set(manifest["blocked_case_ids"]), LEAK)
                require(model.training and not model.encoder.training and not model.act_head.training,
                        "training_mode_regression")
                optimizer.zero_grad(set_to_none=True)
                batch, outputs = forward(model, span, validity, [by_id[i] for i in ids], tok.pad_token_id, device, captured, torch)
                mask = batch["user_state_mask"]
                require(bool(mask.any()) and bool((batch["bio_labels"][~mask] == -100).all()), "loss_mask_invalid")
                losses = {"intent": F.cross_entropy(outputs["typed_logits"].float(), batch["intent_label"]),
                    "span": F.cross_entropy(outputs["span_logits"][mask].float(), batch["bio_labels"][mask]),
                    "validity": F.binary_cross_entropy_with_logits(outputs["validity_logits"].float(), batch["validity_label"])}
                losses["total"] = sum(losses.values())
                shape.require_finite_tensors(losses, device, torch)
                safety = update_step(result, losses["total"], model, parameters, optimizer, device, torch)
                values = {k: float(v.item()) for k, v in losses.items()}
                for k, v in losses.items():
                    sums[k] += v.detach().float() * len(ids)
                result["steps"].append({"step": result["optimizer_steps"], "epoch": epoch,
                    "case_ids": ids, "losses": values, **safety, "vram": smoke.vram(torch, target)})
                if result["optimizer_steps"] == 1:
                    result["vram"]["first_train_batch"] = smoke.vram(torch, target)
                del batch, outputs, losses
            torch.cuda.synchronize(target)
            result["epochs"].append({"epoch": epoch, "steps": 63, "rows": 498,
                "example_weighted_mean_losses": {k: float((v / 498).item()) for k, v in sums.items()},
                "wall_seconds": time.perf_counter() - epoch_started, "vram": smoke.vram(torch, target)})
        result["train_wall_seconds"] = time.perf_counter() - train_started
        require(result["optimizer_steps"] == 189, "optimizer_step_count")
        smoke.check_frozen(model)
        hashes = smoke.group_hashes(model, span, validity)
        initial = result["parameter_hashes_before"]
        require(all(hashes[k] == initial[k] for k in ("encoder", "act_head")), "frozen_parameters_changed")
        require(all(hashes[k] != initial[k] for k in ("typed", "span", "validity")), "trainable_parameters_unchanged")
        result["parameter_hashes_after"] = hashes
        result["vram"]["post_training"] = smoke.vram(torch, target)
        optimizer.zero_grad(set_to_none=True)
        require_absent_checkpoint()
        CHECKPOINT_DIR.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_DIR.mkdir(exist_ok=False)
        path = CHECKPOINT_DIR / "final.pt"
        binding = {"config": json.loads(smoke.canonical_bytes(CONFIG)), "seed": 1729,
                   "train_selection": manifest, "identities": before}
        digest = save_checkpoint(path, binding, result["optimizer_steps"], model, span, validity, optimizer, torch)
        result["checkpoint"] = {"path": "<external-adaptation-root>/" + BASE + "/final.pt",
            "sha256": digest, "size_bytes": path.stat().st_size, "schema": "laya-small-adaptation-final-v1",
            "completed_steps": 189, "contains_frozen_weights": False}
        model_type, encoder, act_head, temperature = type(model), model.encoder, model.act_head, model.temperature
        del model, span, validity, optimizer, parameters
        model = model_type(encoder, cfg.get("head_layers", 2), len(cfg.get("act_costs", {})) + 1)
        model.act_head, model.temperature = act_head, temperature
        model.to(target)
        span, validity = smoke.new_heads(model, device, torch)
        smoke.freeze_policy(model)
        restore_checkpoint(path, digest, binding, model, span, validity, torch)
        model.eval()
        span.eval()
        validity.eval()
        restored = smoke.group_hashes(model, span, validity)
        require(restored == hashes, "final_checkpoint_reload_hash_mismatch")
        smoke.check_frozen(model)
        require(all(str(p.device) == device for module in (model, span, validity) for p in module.parameters()), "reload_device_mismatch")
        result["checkpoint"].update(reload_verified=True, all_trainable_objects_recreated=True,
                                    restored_parameter_hashes=restored)
        result["vram"]["after_reload"] = smoke.vram(torch, target)
        torch.cuda.reset_peak_memory_stats(target)
        val_started = time.perf_counter()
        def infer(rows: list[Any], items: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
            require(all(r.ai_scope == "supported" for r in rows), LEAK)
            require(all(not m.training for m in (model, span, validity)), "validation_not_eval")
            with torch.no_grad():
                _, outputs = forward(model, span, validity, items, tok.pad_token_id, device, captured, torch)
                typed = outputs["typed_logits"].float().argmax(-1).tolist()
                probs = outputs["typed_logits"].float().softmax(-1)[:, 0].tolist()
                valid = outputs["validity_logits"].float().sigmoid().tolist()
                tags = outputs["span_logits"].argmax(-1).tolist()
            predictions = []
            for r, item, index, probability, labels in zip(rows, items, typed, valid, tags):
                mask = item["user_state_mask"]
                # Argmax labels are consumed only at user-state positions.
                labels = [label if allowed else 0 for label, allowed in zip(labels, mask)]
                predictions.append(decode(index, probability, labels, mask, item["token_offsets"], r.utterance))
            return predictions, [{"typed_play_probability": a, "validity_probability": b} for a, b in zip(probs, valid)]
        run_validation(result, val_rows, val_rendered, infer)
        torch.cuda.synchronize(target)
        result["validation_wall_seconds"] = time.perf_counter() - val_started
        result["vram"]["validation_peak"] = smoke.vram(torch, target)
        require(smoke.group_hashes(model, span, validity) == hashes, "validation_parameter_mutation")
        result["vram"]["final"] = smoke.vram(torch, target)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, (smoke.DataBoundaryError, pinned.GateError, adapter.ShapeError)) else type(exc).__name__
        result.update(status=reason if reason in (SELECTOR, LEAK) else DATA if isinstance(exc, smoke.DataBoundaryError) else BLOCK,
                      blocker=reason)
    finally:
        if hook is not None:
            hook.remove()
        if before is not None:
            try:
                _, _, after_data = verified_data()
                after = smoke.immutable_identity(after_data)
                result["identities_after"] = after
                require(before == after, "immutable_identity_changed")
            except Exception as exc:
                result.update(status=BLOCK, blocker=str(exc) if isinstance(exc, (smoke.DataBoundaryError, pinned.GateError)) else type(exc).__name__)
        if path is not None and path.exists():
            try:
                path.chmod(stat.S_IREAD)
                CHECKPOINT_DIR.chmod(stat.S_IREAD)
                require(bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
                        and bool(CHECKPOINT_DIR.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY), "checkpoint_readonly_failed")
                result["checkpoint"]["retained_research_only_readonly"] = True
            except Exception:
                result.update(status=BLOCK, blocker="checkpoint_readonly_failed")
    result["canonical_result_sha256"] = canonical_hash(result)
    return result


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve(), "qualified_python_mismatch")
    require_absent_checkpoint()
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    completed = runner(pinned.child_command(script=Path(__file__).resolve()), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=False, env=env, timeout=1800)
    try:
        matches = [line[len(PREFIX):] for line in completed.stdout.decode("utf-8", "strict").splitlines() if line.startswith(PREFIX)]
        require(len(matches) == 1, "child_result_missing_or_ambiguous")
        result = json.loads(matches[0])
        require((result["status"] == PASS) == (completed.returncode == 0), "child_exit_status")
        unsigned = dict(result)
        digest = unsigned.pop("canonical_result_sha256")
        require(canonical_hash(unsigned) == digest, "child_result_hash")
        return result
    except (UnicodeError, ValueError, KeyError, pinned.GateError):
        return {"status": BLOCK, "blocker": "child_result_unreadable", "child_returncode": completed.returncode}


def main() -> int:
    try:
        if sys.argv[1:] == ["--child"]:
            result = child()
            print(PREFIX + json.dumps(result, ensure_ascii=True, sort_keys=True))
        elif sys.argv[1:] in ([], ["--preflight"], ["--live"]):
            result = parent() if sys.argv[1:] == ["--live"] else preflight()
            print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        else:
            raise SystemExit("unexpected_arguments")
    except Exception as exc:
        result = {"status": DATA if isinstance(exc, smoke.DataBoundaryError) else BLOCK,
                  "blocker": str(exc) if isinstance(exc, (smoke.DataBoundaryError, pinned.GateError)) else type(exc).__name__}
        print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in (PASS, "DATA_PREFLIGHT_PASSED_NO_MODEL_COMPUTE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
