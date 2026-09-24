"""Fail-closed RX 9070 XT tensor smoke for the Stage B hardware sub-gate.

This probes only tiny synthetic tensors. It does not load models or corpus data,
and it does not authorize model compute, training, or production fallback.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable


TARGET_NAME = "AMD Radeon RX 9070 XT"
TARGET_ARCHITECTURE = "gfx1201"
REPORT_VERSION = "stage-b-rx9070xt-tensor-smoke-v1"
AUTHORITY_FLAGS = {
    "training_authorized": False,
    "model_compute_authorized": False,
    "semantic_memory_enabled": False,
    "local_ai_fallback_approved": False,
}
REMAINING_GATES = (
    "laya load and device readback",
    "decider load and device readback",
    "model forward and backward",
    "adapter smoke",
    "training-pipeline smoke",
    "Stage B candidate qualification",
    "held-out quality result",
    "latency acceptance",
    "training authorization",
    "model compute authorization",
    "production fallback approval",
)


class HardwarePreflightError(RuntimeError):
    """The exact Stage B accelerator target was not safely qualified."""


@dataclass(frozen=True)
class AcceleratorDevice:
    index: int
    name: str
    architecture: str | None
    total_memory_bytes: int
    device_type: str


@dataclass(frozen=True)
class TensorSmoke:
    selected_index: int
    dtype: str
    shape: tuple[int, int]
    readback: tuple[tuple[float, ...], ...]
    checksum: float
    all_values_finite: bool
    gpu_tensor_devices: tuple[str, ...]
    peak_allocated_bytes: int | None
    peak_reserved_bytes: int | None
    elapsed_seconds: float
    cpu_fallback: bool


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().split())


def enumerate_accelerators(torch_module: Any) -> tuple[AcceleratorDevice, ...]:
    """Read every PyTorch-visible accelerator; no default index is trusted."""

    if not torch_module.cuda.is_available():
        raise HardwarePreflightError("PyTorch reports no available accelerator")
    count = torch_module.cuda.device_count()
    if not isinstance(count, int) or count <= 0:
        raise HardwarePreflightError("PyTorch reports no accelerator devices")
    devices: list[AcceleratorDevice] = []
    for index in range(count):
        properties = torch_module.cuda.get_device_properties(index)
        name = torch_module.cuda.get_device_name(index)
        property_name = getattr(properties, "name", None)
        architecture = getattr(properties, "gcnArchName", None)
        total_memory = getattr(properties, "total_memory", None)
        device_type = torch_module.device(f"cuda:{index}").type
        if (
            not isinstance(name, str)
            or not name.strip()
            or property_name != name
            or not isinstance(total_memory, int)
            or total_memory <= 0
            or device_type != "cuda"
            or (architecture is not None and not isinstance(architecture, str))
        ):
            raise HardwarePreflightError("PyTorch device identity is incomplete or inconsistent")
        devices.append(AcceleratorDevice(index, name, architecture, total_memory, device_type))
    return tuple(devices)


def select_target(devices: tuple[AcceleratorDevice, ...]) -> AcceleratorDevice:
    """Require one RX 9070 XT with gfx1201 when architecture is exposed."""

    matches = [device for device in devices if _normalized_name(device.name) == _normalized_name(TARGET_NAME)]
    if len(matches) != 1:
        raise HardwarePreflightError("exactly one RX 9070 XT target is required")
    selected = matches[0]
    if selected.device_type != "cuda":
        raise HardwarePreflightError("selected device is not a PyTorch accelerator")
    if selected.architecture is not None and selected.architecture.casefold() != TARGET_ARCHITECTURE:
        raise HardwarePreflightError("RX 9070 XT architecture differs from gfx1201")
    if selected.total_memory_bytes <= 0:
        raise HardwarePreflightError("RX 9070 XT memory identity is unavailable")
    return selected


def _peak_bytes(torch_module: Any, method_name: str, device: Any) -> int | None:
    method = getattr(torch_module.cuda, method_name, None)
    if method is None:
        return None
    try:
        value = method(device)
    except (RuntimeError, TypeError, AttributeError):
        return None
    return value if isinstance(value, int) and value >= 0 else None


def run_tensor_smoke(torch_module: Any, selected: AcceleratorDevice) -> TensorSmoke:
    """Run one 4x4 FP32 identity matmul on the selected GPU only."""

    device = torch_module.device(f"cuda:{selected.index}")
    if device.type != "cuda" or device.index != selected.index:
        raise HardwarePreflightError("selected PyTorch device differs from the target index")
    start = time.perf_counter()
    a = torch_module.arange(16, dtype=torch_module.float32, device=device).reshape(4, 4)
    b = torch_module.eye(4, dtype=torch_module.float32, device=device)
    c = a @ b
    gpu_devices = (a.device, b.device, c.device)
    if any(item.type != "cuda" or item.index != selected.index for item in gpu_devices):
        raise HardwarePreflightError("a GPU-side tensor was placed on CPU or another device")
    torch_module.cuda.synchronize(device)
    readback = tuple(tuple(float(value) for value in row) for row in c.cpu().tolist())
    elapsed = time.perf_counter() - start
    if len(readback) != 4 or any(len(row) != 4 for row in readback):
        raise HardwarePreflightError("tensor readback shape differs from 4x4")
    values = tuple(value for row in readback for value in row)
    if not all(math.isfinite(value) for value in values):
        raise HardwarePreflightError("tensor readback contains NaN or Inf")
    if values != tuple(float(value) for value in range(16)):
        raise HardwarePreflightError("tensor matmul readback differs from the expected matrix")
    return TensorSmoke(
        selected_index=selected.index,
        dtype="float32",
        shape=(4, 4),
        readback=readback,
        checksum=sum(values),
        all_values_finite=True,
        gpu_tensor_devices=tuple(str(item) for item in gpu_devices),
        peak_allocated_bytes=_peak_bytes(torch_module, "max_memory_allocated", device),
        peak_reserved_bytes=_peak_bytes(torch_module, "max_memory_reserved", device),
        elapsed_seconds=elapsed,
        cpu_fallback=False,
    )


def build_report(
    *, torch_version: str, hip_version: str, cuda_version: str | None,
    devices: tuple[AcceleratorDevice, ...], selected: AcceleratorDevice, smoke: TensorSmoke,
) -> dict[str, Any]:
    """Emit only allowlisted, sanitized evidence and closed authority flags."""

    if not hip_version or selected not in devices or smoke.selected_index != selected.index or smoke.cpu_fallback:
        raise HardwarePreflightError("GPU evidence is incomplete or inconsistent")
    if smoke.gpu_tensor_devices != (f"cuda:{selected.index}",) * 3:
        raise HardwarePreflightError("tensor device readback differs from the selected GPU")
    values = tuple(value for row in smoke.readback for value in row)
    if (
        smoke.dtype != "float32"
        or smoke.shape != (4, 4)
        or len(smoke.readback) != 4
        or any(len(row) != 4 for row in smoke.readback)
        or not smoke.all_values_finite
        or not all(math.isfinite(value) for value in values)
        or values != tuple(float(value) for value in range(16))
        or smoke.checksum != 120.0
    ):
        raise HardwarePreflightError("tensor result is not the required finite 4x4 identity product")
    return {
        "report_version": REPORT_VERSION,
        "result": "RX9070XT_TENSOR_SMOKE_PASSED",
        "torch_version": torch_version,
        "hip_version": hip_version,
        "cuda_version": cuda_version,
        "visible_accelerators": [asdict(device) for device in devices],
        "selected_device": asdict(selected),
        "tensor_smoke": asdict(smoke),
        "authority_flags": dict(AUTHORITY_FLAGS),
        "remaining_unproven": list(REMAINING_GATES),
    }


def qualify_torch(
    torch_module: Any, *, smoke_runner: Callable[[Any, AcceleratorDevice], TensorSmoke] = run_tensor_smoke,
) -> dict[str, Any]:
    """Enumerate, select, and run one bounded GPU operation."""

    hip_version = getattr(torch_module.version, "hip", None)
    if not isinstance(hip_version, str) or not hip_version:
        raise HardwarePreflightError("PyTorch build has no ROCm/HIP version evidence")
    devices = enumerate_accelerators(torch_module)
    selected = select_target(devices)
    smoke = smoke_runner(torch_module, selected)
    return build_report(
        torch_version=str(torch_module.__version__), hip_version=hip_version,
        cuda_version=getattr(torch_module.version, "cuda", None),
        devices=devices, selected=selected, smoke=smoke,
    )


def main() -> int:
    try:
        from local_ai_stage_b_held_out_seal import verify_seal

        seal = verify_seal()
        if (
            seal["final_split_assigned"] is not True
            or seal["held_out_sealed"] is not True
            or any(seal[flag] is not False for flag in AUTHORITY_FLAGS)
        ):
            raise HardwarePreflightError("frozen Stage B seal has unauthorized flags")
        import torch

        report = qualify_torch(torch)
        report["frozen_stage_b_seal"] = {
            "seal_manifest_sha256": seal["seal_manifest_sha256"],
            "sealed_row_count": seal["sealed_row_count"],
            "sealed_group_count": seal["sealed_group_count"],
            "final_split_assigned": seal["final_split_assigned"],
            "held_out_sealed": seal["held_out_sealed"],
        }
    except HardwarePreflightError as exc:
        print(json.dumps({"result": "RX9070XT_TENSOR_SMOKE_BLOCKED", "reason": str(exc)}, sort_keys=True))
        return 1
    except Exception as exc:
        # Runtime errors can contain local paths; report only the exception type.
        print(json.dumps({"result": "RX9070XT_TENSOR_SMOKE_BLOCKED", "reason": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
