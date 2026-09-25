"""Offline Laya load and RX 9070 XT residency check; no model forward pass."""

from __future__ import annotations

import hashlib
import json
import locale
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from local_ai_stage_b_rx9070xt_hardware_preflight import (
    AUTHORITY_FLAGS,
    enumerate_accelerators,
    select_target,
)


PYTHON = Path(r"D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe")
SOURCE = Path(r"D:\ai\siri-spec\runtime\ai_poc\upstream-batch-2b\laya")
MODEL = Path(r"D:\ai\ai\laya")
SOURCE_REVISION = "42626c348753fbb17572a813127df2278a1ec527"
MODEL_REVISION = "052592a15d198d9ad47da779604259b10b47b7aa"
WEIGHT_SHA = "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"
ARTIFACT_SHA = "eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf"
SEAL_SHA = "5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef"
EXPECTED_PARAMETER_ELEMENTS = 321_908_995
EXPECTED_TEMPERATURE_BUFFER_ELEMENTS = 3
EXPECTED_CHECKPOINT_STATE_ELEMENTS = 321_908_998
RESULT_PREFIX = "STAGE_B_LAYA_RESULT="
EXPECTED_PACKAGES = {
    "pip": "26.2.1",
    "transformers": "4.57.6",
    "safetensors": "0.7.0",
    "huggingface-hub": "0.36.2",
    "numpy": "2.3.5",
}
REQUIRED_MODEL_FILES = {
    "model.safetensors", "rl_agent_config.json", "encoder/config.json",
    "tokenizer/tokenizer_config.json", "tokenizer/tokenizer.json",
}


class GateError(RuntimeError):
    """A fixed identity or residency requirement failed."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise GateError(reason)


def require_utf8_mode(mode: int) -> None:
    require(mode == 1, "child_utf8_mode_missing")


def child_command(python: Path = PYTHON, script: Path | None = None) -> list[str]:
    return [str(python), "-B", "-X", "utf8", str(script or Path(__file__).resolve()), "--child"]


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(SOURCE), *args], capture_output=True, check=True, text=False,
    )
    return completed.stdout.decode("utf-8", "strict").strip()


def source_identity() -> str:
    require(SOURCE.is_dir() and not SOURCE.is_symlink()
            and not getattr(SOURCE, "is_junction", lambda: False)(), "source_missing_or_redirected")
    revision = _git("rev-parse", "HEAD")
    require(revision == SOURCE_REVISION, "source_revision_mismatch")
    require(not _git("status", "--porcelain=v1"), "source_checkout_dirty")
    require(_git("remote", "get-url", "origin") == "https://github.com/NandhaKishorM/laya.git", "source_remote_mismatch")
    return revision


def package_inventory() -> str:
    completed = subprocess.run(
        [str(PYTHON), "-B", "-m", "pip", "freeze"], capture_output=True,
        check=True, text=False,
    )
    return hashlib.sha256(completed.stdout).hexdigest()


def artifact_inventory(root: Path = MODEL) -> tuple[list[dict[str, Any]], str]:
    require(root.is_dir() and not root.is_symlink()
            and not getattr(root, "is_junction", lambda: False)(), "model_directory_missing_or_redirected")
    rows: list[dict[str, Any]] = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            require(not path.is_symlink() and not getattr(path, "is_junction", lambda: False)(),
                    "model_directory_redirected")
        for name in files:
            path = Path(directory) / name
            require(path.is_file() and not path.is_symlink(), "model_file_missing_or_redirected")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            rows.append({
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": digest.hexdigest(),
            })
    rows.sort(key=lambda row: row["path"])
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return rows, hashlib.sha256(encoded).hexdigest()


def model_identity(rows: list[dict[str, Any]], aggregate: str) -> None:
    by_path = {row["path"]: row for row in rows}
    require(len(rows) == 11 and aggregate == ARTIFACT_SHA, "canonical_artifact_identity_mismatch")
    require(REQUIRED_MODEL_FILES <= by_path.keys(), "required_model_file_missing")
    require(by_path["model.safetensors"]["sha256"] == WEIGHT_SHA, "primary_weight_sha_mismatch")
    metadata = MODEL / ".cache" / "huggingface" / "download"
    for name in REQUIRED_MODEL_FILES:
        path = metadata / (name + ".metadata")
        require(path.is_file(), "model_revision_metadata_missing")
        require(path.read_bytes().splitlines()[0].decode("ascii") == MODEL_REVISION, "model_revision_mismatch")
    config = json.loads((MODEL / "tokenizer" / "tokenizer_config.json").read_bytes().decode("utf-8"))
    require(config.get("tokenizer_class") not in (None, "TokenizersBackend"), "tokenizer_fix_would_write")
    require(not isinstance(config.get("extra_special_tokens"), list), "tokenizer_fix_would_write")


def checkpoint_header() -> list[dict[str, Any]]:
    """Inspect tensor slices only; never materialize checkpoint payloads."""
    from safetensors import safe_open

    with safe_open(str(MODEL / "model.safetensors"), framework="pt", device="cpu") as handle:
        return [{"key": key, "shape": handle.get_slice(key).get_shape(),
                 "dtype": handle.get_slice(key).get_dtype(),
                 "elements": math.prod(handle.get_slice(key).get_shape())}
                for key in sorted(handle.keys())]


def validate_checkpoint_header(rows: list[dict[str, Any]]) -> dict[str, int]:
    temperature = [row for row in rows if row["key"] == "temperature"]
    require(len(temperature) == 1 and temperature[0]["shape"] == [3]
            and temperature[0]["dtype"] == "F32"
            and temperature[0]["elements"] == EXPECTED_TEMPERATURE_BUFFER_ELEMENTS,
            "temperature_checkpoint_mismatch")
    total = sum(row["elements"] for row in rows)
    require(total == EXPECTED_CHECKPOINT_STATE_ELEMENTS
            and total - temperature[0]["elements"] == EXPECTED_PARAMETER_ELEMENTS,
            "checkpoint_element_count_mismatch")
    return {"checkpoint_tensor_keys": len(rows), "checkpoint_state_element_count": total,
            "checkpoint_parameter_elements": total - temperature[0]["elements"]}


def require_unchanged(before: Any, after: Any, reason: str) -> None:
    require(before == after, reason)


def select_device(devices: tuple[Any, ...]) -> str:
    require(not any("nvidia" in item.name.casefold() for item in devices), "nvidia_device_visible")
    selected = select_target(devices)
    require(selected.architecture == "gfx1201", "target_architecture_unavailable")
    return f"cuda:{selected.index}"


def collect_residency(agent: Any, device: str) -> dict[str, Any]:
    reported = str(agent.device)
    parameters = list(agent.model.named_parameters())
    buffers = list(agent.model.named_buffers())
    parameter_devices = sorted({str(value.device) for _, value in parameters})
    buffer_devices = sorted({str(value.device) for _, value in buffers})
    state = agent.model.state_dict()
    persistent_buffers = [(name, value) for name, value in buffers if name in state]
    count = sum(value.numel() for _, value in parameters)
    return {
        "laya_reported_device": reported,
        "parameter_devices": parameter_devices,
        "buffer_devices": buffer_devices,
        "parameter_count": count,
        "persistent_buffer_count": sum(value.numel() for _, value in persistent_buffers),
        "persistent_temperature_buffer_count": sum(value.numel() for name, value in persistent_buffers if name == "temperature"),
        "checkpoint_state_element_count": sum(value.numel() for value in state.values()),
        "state_keys_match_parameters_and_buffers": set(state) == ({name for name, _ in parameters} | {name for name, _ in persistent_buffers}),
        "persistent_buffer_names": sorted(name for name, _ in persistent_buffers),
        "trainable_parameter_count": sum(value.numel() for _, value in parameters if value.requires_grad),
        "parameter_dtypes": sorted({str(value.dtype) for _, value in parameters}),
        "buffer_dtypes": sorted({str(value.dtype) for _, value in buffers}),
        "checkpoint_compatibility": "strict_load_state_dict_succeeded",
        "cpu_fallback": any(value.startswith("cpu") for value in [reported, *parameter_devices, *buffer_devices]),
    }


def validate_residency(observed: dict[str, Any], device: str) -> None:
    require(device.startswith("cuda:") and device[5:].isdigit(), "selected_device_not_indexed")
    require(observed["laya_reported_device"] == device, "laya_device_mismatch_or_cpu_fallback")
    require(observed["parameter_devices"] == [device], "parameter_residency_mismatch")
    require(all(value == device for value in observed["buffer_devices"]), "buffer_residency_mismatch")
    require(observed["parameter_count"] == EXPECTED_PARAMETER_ELEMENTS, "parameter_count_mismatch")
    require(observed["persistent_buffer_names"] == ["temperature"]
            and observed["persistent_temperature_buffer_count"] == EXPECTED_TEMPERATURE_BUFFER_ELEMENTS
            and observed["persistent_buffer_count"] == EXPECTED_TEMPERATURE_BUFFER_ELEMENTS,
            "persistent_buffer_mismatch")
    require(observed["state_keys_match_parameters_and_buffers"]
            and observed["checkpoint_state_element_count"] == EXPECTED_CHECKPOINT_STATE_ELEMENTS,
            "checkpoint_state_mismatch")


def residency(agent: Any, device: str) -> dict[str, Any]:
    observed = collect_residency(agent, device)
    validate_residency(observed, device)
    return observed


def child() -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "LAYA_MODEL_LOAD_NEW_BLOCKER",
        "root_cause_classification": "OTHER_DEPENDENCY_CP950",
        "utf8_mode": sys.flags.utf8_mode,
        "preferred_encoding": locale.getpreferredencoding(False),
        "default_encoding": sys.getdefaultencoding(),
        "stdout_encoding": sys.stdout.encoding,
        "stderr_encoding": sys.stderr.encoding,
        "authority_flags": dict(AUTHORITY_FLAGS),
    }
    before_rows = None
    before_packages = None
    try:
        require_utf8_mode(sys.flags.utf8_mode)
        require(Path(sys.executable).resolve() == PYTHON.resolve(), "qualified_python_mismatch")
        require(sys.version_info[:3] == (3, 14, 7), "python_version_mismatch")
        from importlib.metadata import version

        for name, expected in EXPECTED_PACKAGES.items():
            require(version(name) == expected, "package_version_mismatch")
        import torch

        require(torch.__version__ == "2.13.0+rocm10.0.0", "torch_version_mismatch")
        require(torch.version.hip == "7.15.26333" and torch.version.cuda is None, "rocm_build_mismatch")
        before_packages = package_inventory()
        result["venv_inventory_sha256_before"] = before_packages
        result["source_revision"] = source_identity()
        result["source_clean"] = True
        before_rows, before_sha = artifact_inventory()
        result["canonical_artifact_pre_sha256"] = before_sha
        model_identity(before_rows, before_sha)
        result.update(validate_checkpoint_header(checkpoint_header()))
        devices = enumerate_accelerators(torch)
        device = select_device(devices)
        selected = next(item for item in devices if item.index == int(device[5:]))
        result.update({
            "visible_devices": [vars(item) for item in devices],
            "selected_device": device,
            "selected_device_name": selected.name,
            "selected_device_arch": selected.architecture,
        })
        target = torch.device(device)
        torch.cuda.reset_peak_memory_stats(target)
        result["baseline_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["baseline_reserved_bytes"] = torch.cuda.memory_reserved(target)
        sys.path.insert(0, str(SOURCE))
        import laya

        require(Path(laya.__file__).resolve() == SOURCE / "laya" / "__init__.py", "unpinned_laya_import")
        started = time.perf_counter()
        agent = laya.load(str(MODEL), device=device)
        torch.cuda.synchronize(target)
        result["load_seconds"] = round(time.perf_counter() - started, 3)
        result["after_load_allocated_bytes"] = torch.cuda.memory_allocated(target)
        result["after_load_reserved_bytes"] = torch.cuda.memory_reserved(target)
        result["peak_allocated_bytes"] = torch.cuda.max_memory_allocated(target)
        result["peak_reserved_bytes"] = torch.cuda.max_memory_reserved(target)
        result.update(collect_residency(agent, device))
        validate_residency(result, device)
        result["status"] = "LAYA_RX9070XT_MODEL_LOAD_READBACK_PASSED"
    except UnicodeDecodeError as exc:
        result.update(status="LAYA_UTF8_PROCESS_FIX_FAILED" if exc.encoding == "cp950" else "LAYA_MODEL_LOAD_NEW_BLOCKER",
                      blocker=type(exc).__name__, blocker_detail=str(exc)[:200])
    except GateError as exc:
        result.update(blocker=str(exc), blocker_detail=str(exc)[:200])
    except Exception as exc:
        result.update(blocker=type(exc).__name__, blocker_detail=str(exc)[:200])
    finally:
        if before_rows is not None:
            try:
                after_rows, after_sha = artifact_inventory()
                result["canonical_artifact_post_sha256"] = after_sha
                result["canonical_artifact_unchanged"] = before_rows == after_rows
                require_unchanged(before_rows, after_rows, "canonical_artifact_mutated")
            except Exception as exc:
                result.update(status="LAYA_MODEL_LOAD_NEW_BLOCKER", blocker=type(exc).__name__, blocker_detail=str(exc)[:200])
        if before_packages is not None:
            try:
                after_packages = package_inventory()
                result["venv_inventory_sha256_after"] = after_packages
                result["venv_unchanged"] = before_packages == after_packages
                require_unchanged(before_packages, after_packages, "package_inventory_mutated")
                result["source_revision"] = source_identity()
                result["source_clean"] = True
            except Exception as exc:
                result.update(status="LAYA_MODEL_LOAD_NEW_BLOCKER", blocker=type(exc).__name__, blocker_detail=str(exc)[:200])
    return result


def parent(runner: Any = subprocess.run) -> dict[str, Any]:
    from local_ai_stage_b_held_out_seal import verify_seal

    require(Path(sys.executable).resolve() == PYTHON.resolve(), "qualified_python_mismatch")
    seal = verify_seal()
    require(seal["seal_manifest_sha256"] == SEAL_SHA and seal["sealed_row_count"] == 600
            and seal["sealed_group_count"] == 100 and seal["final_split_assigned"] is True
            and seal["held_out_sealed"] is True, "frozen_stage_b_seal_mismatch")
    require(all(seal[key] is False for key in AUTHORITY_FLAGS), "stage_b_authority_flag_changed")
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    completed = runner(child_command(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=False, env=env, timeout=240)
    try:
        lines = completed.stdout.decode("utf-8", "strict").splitlines()
        matches = [line[len(RESULT_PREFIX):] for line in lines if line.startswith(RESULT_PREFIX)]
        require(len(matches) == 1, "child_result_missing_or_ambiguous")
        result = json.loads(matches[0])
        require(isinstance(result, dict), "child_result_invalid")
    except (UnicodeError, ValueError, GateError):
        return {"status": "LAYA_MODEL_LOAD_NEW_BLOCKER", "blocker": "child_result_unreadable",
                "child_returncode": completed.returncode, "authority_flags": dict(AUTHORITY_FLAGS)}
    valid_success = completed.returncode == 0 and result.get("status") == "LAYA_RX9070XT_MODEL_LOAD_READBACK_PASSED"
    valid_failure = completed.returncode != 0 and result.get("status") in ("LAYA_MODEL_LOAD_NEW_BLOCKER", "LAYA_UTF8_PROCESS_FIX_FAILED") and isinstance(result.get("blocker"), str) and bool(result["blocker"])
    if not (valid_success or valid_failure):
        result.update(status="LAYA_MODEL_LOAD_NEW_BLOCKER", blocker="child_nonzero_exit")
    result["child_returncode"] = completed.returncode
    result["frozen_stage_b_seal_sha256"] = SEAL_SHA
    return result


def main() -> int:
    if sys.argv[1:] == ["--child"]:
        result = child()
        print(RESULT_PREFIX + json.dumps(result, ensure_ascii=True, sort_keys=True))
    elif not sys.argv[1:]:
        try:
            result = parent()
        except Exception as exc:
            result = {"status": "LAYA_MODEL_LOAD_NEW_BLOCKER", "blocker": type(exc).__name__,
                      "blocker_detail": str(exc)[:200], "authority_flags": dict(AUTHORITY_FLAGS)}
        print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        raise SystemExit("unexpected arguments")
    return 0 if result["status"] == "LAYA_RX9070XT_MODEL_LOAD_READBACK_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
