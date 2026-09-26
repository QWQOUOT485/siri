"""One bounded research-only Laya head shape smoke; never trains or saves a model."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import local_ai_stage_b_laya_adapter as adapter
import local_ai_stage_b_laya_model_load_preflight as pinned
from local_ai_stage_b_held_out_seal import verify_seal
from local_ai_stage_b_rx9070xt_hardware_preflight import AUTHORITY_FLAGS, enumerate_accelerators


RESULT_PREFIX = "STAGE_B_LAYA_HEAD_SMOKE_RESULT="
PASS = "LAYA_RX9070XT_HEAD_ONLY_FORWARD_BACKWARD_SMOKE_PASSED"
BLOCK = "LAYA_HEAD_SHAPE_SMOKE_NEW_BLOCKER"
FIXTURE_SHA = "f632172af7a0ffce4c0a315d18bb353c30720ccf60581f7ada73f2fb892195a0"
SEED = 1729


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise pinned.GateError(reason)


def verified_seal() -> dict[str, Any]:
    seal = verify_seal()
    require(seal["seal_manifest_sha256"] == pinned.SEAL_SHA
            and seal["sealed_row_count"] == 600 and seal["sealed_group_count"] == 100
            and seal["final_split_assigned"] is True and seal["held_out_sealed"] is True
            and all(seal[key] is False for key in AUTHORITY_FLAGS), "stage_b_seal_mismatch")
    return seal


def fixture_and_render(tok: Any, build_sequence: Any, cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        adapter.require(hashlib.sha256(adapter.FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA,
                        "fixture_identity_mismatch")
        rows = adapter.load_fixture()
        items = adapter.validate_rendering(tok, build_sequence, rows,
                 max_len=cfg.get("max_len", 512), head_max_len=cfg.get("head_max_len", 192))
    except adapter.ShapeError as exc:
        if str(exc) == "STOP_LAYA_RENDERING_DIVERGENCE":
            raise
        raise adapter.ShapeError("STOP_LAYA_SHAPE_FIXTURE_INVALID:" + str(exc)) from exc
    adapter.require([row["row_id"] for row in rows if row["row_id"] in adapter.LIVE_IDS]
                    == list(adapter.LIVE_IDS), "fixed_live_batch_missing")
    return rows, items


def shape_contract(shapes: dict[str, tuple[int, ...]], batch: int = 8) -> tuple[int, int]:
    typed = shapes["typed_logits"]
    action = shapes["action_logits"]
    hidden = shapes["hidden_states"]
    span = shapes["span_logits"]
    validity = shapes["validity_logits"]
    mask = shapes["user_state_mask"]
    require(typed == (batch, 2) and len(action) == 2 and action[0] == batch,
            "typed_or_action_shape_mismatch")
    require(len(hidden) == 3 and hidden[0] == batch and hidden[1] > 0 and hidden[2] > 0,
            "hidden_shape_mismatch")
    require(span == (batch, hidden[1], 7) and mask == (batch, hidden[1])
            and validity in ((batch,), (batch, 1)), "span_validity_or_mask_shape_mismatch")
    return hidden[1], hidden[2]


def batch_tensors(items: list[dict[str, Any]], pad_id: int, device: str, torch: Any) -> dict[str, Any]:
    length = max(len(item["input_ids"]) for item in items)
    def padded(key: str, fill: int | bool, dtype: Any) -> Any:
        return torch.tensor([item[key] + [fill] * (length - len(item[key])) for item in items],
                            dtype=dtype, device=device)
    return {
        "input_ids": padded("input_ids", pad_id, torch.long),
        "attention_mask": padded("attention_mask", 0, torch.long),
        "marker_pos": torch.tensor([item["marker_pos"] for item in items], dtype=torch.long, device=device),
        "marker_mask": torch.tensor([item["marker_mask"] for item in items], dtype=torch.bool, device=device),
        "qtype": torch.zeros(len(items), dtype=torch.long, device=device),
        "user_state_mask": padded("user_state_mask", False, torch.bool),
        "bio_labels": padded("bio_labels", -100, torch.long),
        "intent_label": torch.tensor([item["intent_label"] for item in items], dtype=torch.long, device=device),
        "validity_label": torch.tensor([item["validity_label"] for item in items], dtype=torch.float32, device=device),
    }


def gradient_norm(parameters: Any, device: str, torch: Any) -> float:
    grads = [parameter.grad for parameter in parameters if parameter.grad is not None]
    require(bool(grads), "required_gradient_absent")
    require(all(str(grad.device) == device and bool(torch.isfinite(grad).all()) for grad in grads),
            "gradient_nonfinite_or_wrong_device")
    norm = sum(float(grad.float().square().sum().item()) for grad in grads) ** 0.5
    require(norm > 0, "required_gradient_zero")
    return norm


def require_finite_tensors(tensors: dict[str, Any], device: str, torch: Any) -> None:
    require(all(str(tensor.device) == device and bool(torch.isfinite(tensor).all())
                for tensor in tensors.values()), "output_nonfinite_or_wrong_device")


def freeze_encoder(encoder: Any) -> None:
    for parameter in encoder.parameters():
        parameter.requires_grad_(False)
    require(all(not parameter.requires_grad and parameter.grad is None
                for parameter in encoder.parameters()), "encoder_not_frozen")


def require_no_encoder_grads(encoder: Any) -> None:
    require(all(parameter.grad is None for parameter in encoder.parameters()),
            "encoder_gradient_present")


def child() -> dict[str, Any]:
    result: dict[str, Any] = {"status": BLOCK, "utf8_mode": sys.flags.utf8_mode,
                              "authority_flags": dict(AUTHORITY_FLAGS),
                              "fixture_sha256": FIXTURE_SHA, "live_row_ids": list(adapter.LIVE_IDS),
                              "head_initialization_seed": SEED}
    before_rows = None
    before_packages = None
    hook = None
    model = span_head = validity_head = None
    try:
        pinned.require_utf8_mode(sys.flags.utf8_mode)
        require(Path(sys.executable).resolve() == pinned.PYTHON.resolve(), "qualified_python_mismatch")
        require(sys.version_info[:3] == (3, 14, 7), "python_version_mismatch")
        from importlib.metadata import version
        for name, expected in pinned.EXPECTED_PACKAGES.items():
            require(version(name) == expected, "package_version_mismatch")
        import torch
        import torch.nn.functional as F
        from transformers import AutoTokenizer
        require(torch.__version__ == "2.13.0+rocm10.0.0"
                and torch.version.hip == "7.15.26333" and torch.version.cuda is None,
                "rocm_build_mismatch")
        before_packages = pinned.package_inventory()
        require(before_packages == "3ad25b9f93a161e79a43533a89711eb6a86780aabfd2ed487f2b5629b4837337",
                "venv_inventory_mismatch")
        result["venv_inventory_sha256_before"] = before_packages
        result["source_revision_before"] = pinned.source_identity()
        result["source_clean_before"] = True
        before_rows, before_sha = pinned.artifact_inventory()
        pinned.model_identity(before_rows, before_sha)
        result["canonical_artifact_sha256_before"] = before_sha
        result.update(pinned.validate_checkpoint_header(pinned.checkpoint_header()))
        result["seal_sha256_before"] = verified_seal()["seal_manifest_sha256"]
        sys.path.insert(0, str(pinned.SOURCE))
        from laya.common import build_sequence
        import laya
        require(Path(laya.__file__).resolve() == pinned.SOURCE / "laya" / "__init__.py",
                "unpinned_laya_import")
        cfg = json.loads((pinned.MODEL / "rl_agent_config.json").read_text(encoding="utf-8"))
        tok = AutoTokenizer.from_pretrained(str(pinned.MODEL / "tokenizer"))
        rows, rendered = fixture_and_render(tok, build_sequence, cfg)
        result.update(fixture_rows=len(rows), rendering_equivalent_rows=len(rendered),
                      fixture_slices={str(i): 8 for i in range(1, 9)})
        devices = enumerate_accelerators(torch)
        device = pinned.select_device(devices)
        selected = next(item for item in devices if item.index == int(device[5:]))
        result.update(visible_devices=[vars(item) for item in devices], selected_device=device,
                      selected_device_name=selected.name, selected_device_arch=selected.architecture)
        target = torch.device(device)
        torch.cuda.set_device(target)
        require(torch.cuda.current_device() == selected.index, "current_gpu_not_target")
        torch.cuda.reset_peak_memory_stats(target)
        result["baseline_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["baseline_reserved_bytes"] = torch.cuda.memory_reserved(target)
        started = time.perf_counter()
        agent = laya.load(str(pinned.MODEL), device=device)
        torch.cuda.synchronize(target)
        result["load_seconds"] = round(time.perf_counter() - started, 3)
        result["after_load_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["after_load_reserved_bytes"] = torch.cuda.memory_reserved(target)
        result.update(pinned.collect_residency(agent, device))
        pinned.validate_residency(result, device)
        result["residency_recheck"] = "passed"
        model = agent.model
        freeze_encoder(model.encoder)
        torch.manual_seed(SEED)
        hidden_size = int(model.encoder.config.hidden_size)
        span_head = torch.nn.Linear(hidden_size, 7).to(target)
        validity_head = torch.nn.Linear(hidden_size, 1).to(target)
        chosen = [rendered[next(i for i, row in enumerate(rows) if row["row_id"] == key)]
                  for key in adapter.LIVE_IDS]
        batch = batch_tensors(chosen, tok.pad_token_id, device, torch)
        result["input_batch_shape"] = list(batch["input_ids"].shape)
        result["pre_forward_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["pre_forward_reserved_bytes"] = torch.cuda.memory_reserved(target)
        captured: list[Any] = []
        def capture(_module: Any, _args: Any, output: Any) -> None:
            captured.append(output.last_hidden_state)
        hook = model.encoder.register_forward_hook(capture)
        with torch.autocast(device_type="cuda", dtype=agent.dtype):
            typed, action = model(batch["input_ids"], batch["attention_mask"],
                                  batch["marker_pos"], batch["marker_mask"], batch["qtype"])
        require(len(captured) == 1, "encoder_hook_capture_count")
        hidden = captured[0]
        hook.remove()
        hook = None
        span = span_head(hidden.float())
        validity = validity_head(hidden[:, 0, :].float()).squeeze(-1)
        tensors = {"typed_logits": typed, "action_logits": action, "hidden_states": hidden,
                   "span_logits": span, "validity_logits": validity,
                   "user_state_mask": batch["user_state_mask"]}
        shapes = {name: tuple(tensor.shape) for name, tensor in tensors.items()}
        seq_len, checked_hidden = shape_contract(shapes)
        require(checked_hidden == hidden_size and seq_len == batch["input_ids"].shape[1],
                "hidden_config_or_input_mismatch")
        require_finite_tensors(tensors, device, torch)
        result.update(sequence_length=seq_len, hidden_size=hidden_size)
        result["output_shapes"] = {name: list(shape) for name, shape in shapes.items()}
        result["output_dtypes"] = {name: str(tensor.dtype) for name, tensor in tensors.items()}
        result["output_devices"] = {name: str(tensor.device) for name, tensor in tensors.items()}
        torch.cuda.synchronize(target)
        result["post_forward_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["post_forward_reserved_bytes"] = torch.cuda.memory_reserved(target)
        user_mask = batch["user_state_mask"]
        require(bool(user_mask.any()) and bool((batch["bio_labels"][~user_mask] == -100).all()),
                "span_mask_invalid")
        intent_loss = F.cross_entropy(typed.float(), batch["intent_label"])
        span_loss = F.cross_entropy(span[user_mask].float(), batch["bio_labels"][user_mask])
        validity_loss = F.binary_cross_entropy_with_logits(validity.float(), batch["validity_label"])
        total = intent_loss + span_loss + validity_loss
        require(all(str(x.device) == device and bool(torch.isfinite(x))
                    for x in (intent_loss, span_loss, validity_loss, total)),
                "loss_nonfinite_or_wrong_device")
        result["losses"] = {"intent": float(intent_loss.item()), "span": float(span_loss.item()),
                            "validity": float(validity_loss.item()), "total": float(total.item())}
        total.backward()
        torch.cuda.synchronize(target)
        result["post_backward_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["post_backward_reserved_bytes"] = torch.cuda.memory_reserved(target)
        require_no_encoder_grads(model.encoder)
        typed_parameters = [parameter for name, parameter in model.named_parameters()
                            if name.startswith(("head.", "type_emb.", "scorer."))]
        result["gradient_norms"] = {
            "typed_decision": gradient_norm(typed_parameters, device, torch),
            "span_head": gradient_norm(span_head.parameters(), device, torch),
            "validity_head": gradient_norm(validity_head.parameters(), device, torch),
        }
        result["encoder_gradients_absent"] = True
        result["optimizer_created"] = False
        result["backward_calls"] = 1
        result["peak_allocated_bytes"] = torch.cuda.max_memory_allocated(target)
        result["peak_reserved_bytes"] = torch.cuda.max_memory_reserved(target)
        result["status"] = PASS
    except adapter.ShapeError as exc:
        result["status"] = "STOP_LAYA_RENDERING_DIVERGENCE" if str(exc) == "STOP_LAYA_RENDERING_DIVERGENCE" else "STOP_LAYA_SHAPE_FIXTURE_INVALID"
        result.update(blocker=str(exc), blocker_detail=str(exc)[:200])
    except Exception as exc:
        result.update(blocker=str(exc) if isinstance(exc, pinned.GateError) else type(exc).__name__,
                      blocker_detail=str(exc)[:200])
    finally:
        if hook is not None:
            hook.remove()
        if model is not None:
            model.zero_grad(set_to_none=True)
        if span_head is not None:
            span_head.zero_grad(set_to_none=True)
        if validity_head is not None:
            validity_head.zero_grad(set_to_none=True)
        if before_rows is not None:
            try:
                after_rows, after_sha = pinned.artifact_inventory()
                result["canonical_artifact_sha256_after"] = after_sha
                require(before_rows == after_rows, "canonical_artifact_mutated")
                result["source_revision_after"] = pinned.source_identity()
                result["source_clean_after"] = True
                result["seal_sha256_after"] = verified_seal()["seal_manifest_sha256"]
                after_packages = pinned.package_inventory()
                result["venv_inventory_sha256_after"] = after_packages
                require(after_packages == before_packages, "venv_inventory_mutated")
            except Exception as exc:
                result.update(status=BLOCK, blocker=str(exc), blocker_detail=str(exc)[:200])
    return result


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    require(Path(sys.executable).resolve() == pinned.PYTHON.resolve(), "qualified_python_mismatch")
    verified_seal()
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    completed = runner([str(pinned.PYTHON), "-B", "-X", "utf8", str(Path(__file__).resolve()), "--child"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False, env=env, timeout=300)
    try:
        lines = completed.stdout.decode("utf-8", "strict").splitlines()
        matches = [line[len(RESULT_PREFIX):] for line in lines if line.startswith(RESULT_PREFIX)]
        require(len(matches) == 1, "child_result_missing_or_ambiguous")
        result = json.loads(matches[0])
        require(isinstance(result, dict) and isinstance(result.get("status"), str),
                "child_result_invalid")
    except (UnicodeError, ValueError, pinned.GateError):
        return {"status": BLOCK, "blocker": "child_result_unreadable",
                "child_returncode": completed.returncode, "authority_flags": dict(AUTHORITY_FLAGS)}
    result["child_returncode"] = completed.returncode
    if (result["status"] == PASS) != (completed.returncode == 0):
        result.update(status=BLOCK, blocker="child_exit_status_mismatch")
    return result


def main() -> int:
    if sys.argv[1:] == ["--child"]:
        result = child()
        print(RESULT_PREFIX + json.dumps(result, ensure_ascii=True, sort_keys=True))
    elif not sys.argv[1:]:
        try:
            result = parent()
        except Exception as exc:
            result = {"status": BLOCK, "blocker": type(exc).__name__,
                      "blocker_detail": str(exc)[:200], "authority_flags": dict(AUTHORITY_FLAGS)}
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        raise SystemExit("unexpected arguments")
    return 0 if result["status"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
