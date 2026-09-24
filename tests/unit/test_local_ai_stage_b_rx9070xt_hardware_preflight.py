"""Offline selection and report tests; no GPU, model, or corpus is required."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_rx9070xt_hardware_preflight as hardware  # noqa: E402


IGPU = ("AMD Radeon(TM) Graphics", "gfx1036")
TARGET = ("AMD Radeon RX 9070 XT", "gfx1201")
NVIDIA = ("NVIDIA GeForce RTX 3060", None)


class FakeCuda:
    def __init__(self, device_specs: tuple[tuple[str, str | None], ...], available: bool = True) -> None:
        self.specs = device_specs
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def device_count(self) -> int:
        return len(self.specs)

    def get_device_name(self, index: int) -> str:
        return self.specs[index][0]

    def get_device_properties(self, index: int) -> SimpleNamespace:
        name, architecture = self.specs[index]
        return SimpleNamespace(name=name, gcnArchName=architecture, total_memory=16_000_000_000)


class FakeTorch:
    __version__ = "2.13.0+rocm10.0.0"
    secret_token = "must-never-appear"

    def __init__(self, *specs: tuple[str, str | None], available: bool = True, hip: str | None = "7.15") -> None:
        self.cuda = FakeCuda(specs, available=available)
        self.version = SimpleNamespace(hip=hip, cuda=None)

    @staticmethod
    def device(value: str) -> SimpleNamespace:
        assert value.startswith("cuda:")
        return SimpleNamespace(type="cuda", index=int(value.split(":", 1)[1]))


def _fake_smoke(_torch: FakeTorch, selected: hardware.AcceleratorDevice) -> hardware.TensorSmoke:
    values = tuple(tuple(float(row * 4 + col) for col in range(4)) for row in range(4))
    return hardware.TensorSmoke(
        selected_index=selected.index,
        dtype="float32",
        shape=(4, 4),
        readback=values,
        checksum=120.0,
        all_values_finite=True,
        gpu_tensor_devices=(f"cuda:{selected.index}",) * 3,
        peak_allocated_bytes=1024,
        peak_reserved_bytes=2048,
        elapsed_seconds=0.01,
        cpu_fallback=False,
    )


def test_igpu_at_zero_target_at_one_selects_one_without_default() -> None:
    torch = FakeTorch(IGPU, TARGET)
    selected_indices: list[int] = []

    def capture(fake: FakeTorch, selected: hardware.AcceleratorDevice) -> hardware.TensorSmoke:
        selected_indices.append(selected.index)
        return _fake_smoke(fake, selected)

    report = hardware.qualify_torch(torch, smoke_runner=capture)
    assert selected_indices == [1]
    assert report["selected_device"]["index"] == 1
    assert report["selected_device"]["architecture"] == "gfx1201"
    assert report["visible_accelerators"][0]["architecture"] == "gfx1036"
    assert report["tensor_smoke"]["gpu_tensor_devices"] == ("cuda:1",) * 3
    assert report["tensor_smoke"]["cpu_fallback"] is False
    assert all(value is False for value in report["authority_flags"].values())
    assert "must-never-appear" not in json.dumps(report)
    assert "environ" not in json.dumps(report)


def test_target_at_zero_selects_zero() -> None:
    report = hardware.qualify_torch(FakeTorch(TARGET, IGPU), smoke_runner=_fake_smoke)
    assert report["selected_device"]["index"] == 0
    assert report["tensor_smoke"]["gpu_tensor_devices"] == ("cuda:0",) * 3


@pytest.mark.parametrize("specs", [(), (IGPU,), (NVIDIA,), (IGPU, NVIDIA)])
def test_no_target_igpu_only_and_nvidia_only_fail_closed(specs: tuple[tuple[str, str | None], ...]) -> None:
    with pytest.raises(hardware.HardwarePreflightError):
        hardware.qualify_torch(FakeTorch(*specs), smoke_runner=_fake_smoke)


def test_multiple_matching_targets_are_ambiguous() -> None:
    with pytest.raises(hardware.HardwarePreflightError, match="exactly one"):
        hardware.qualify_torch(FakeTorch(TARGET, TARGET), smoke_runner=_fake_smoke)


def test_wrong_name_with_matching_architecture_is_rejected() -> None:
    with pytest.raises(hardware.HardwarePreflightError, match="exactly one"):
        hardware.qualify_torch(FakeTorch(("AMD Radeon RX 9070", "gfx1201")), smoke_runner=_fake_smoke)


def test_target_name_with_wrong_architecture_is_rejected() -> None:
    with pytest.raises(hardware.HardwarePreflightError, match="architecture"):
        hardware.qualify_torch(FakeTorch((TARGET[0], "gfx1036")), smoke_runner=_fake_smoke)


def test_cpu_only_torch_fails_closed() -> None:
    with pytest.raises(hardware.HardwarePreflightError, match="no available accelerator"):
        hardware.qualify_torch(FakeTorch(TARGET, available=False), smoke_runner=_fake_smoke)


def test_missing_hip_build_evidence_fails_closed() -> None:
    with pytest.raises(hardware.HardwarePreflightError, match="ROCm/HIP"):
        hardware.qualify_torch(FakeTorch(TARGET, hip=None), smoke_runner=_fake_smoke)


def test_missing_architecture_is_reported_without_fabrication() -> None:
    report = hardware.qualify_torch(FakeTorch((TARGET[0], None)), smoke_runner=_fake_smoke)
    assert report["selected_device"]["architecture"] is None


def test_report_rejects_cpu_fallback_or_wrong_tensor_device() -> None:
    torch = FakeTorch(IGPU, TARGET)
    devices = hardware.enumerate_accelerators(torch)
    selected = hardware.select_target(devices)
    smoke = _fake_smoke(torch, selected)
    from dataclasses import replace

    for changed in (
        replace(smoke, cpu_fallback=True),
        replace(smoke, gpu_tensor_devices=("cuda:0",) * 3),
        replace(smoke, checksum=119.0),
        replace(smoke, readback=((float("nan"),) * 4,) * 4),
    ):
        with pytest.raises(hardware.HardwarePreflightError, match="incomplete|tensor device|tensor result"):
            hardware.build_report(
                torch_version=torch.__version__, hip_version="7.15", cuda_version=None,
                devices=devices, selected=selected, smoke=changed,
            )


def test_cli_fails_before_torch_if_frozen_seal_flags_drift(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "local_ai_stage_b_held_out_seal", SimpleNamespace(verify_seal=lambda: {
        "final_split_assigned": True,
        "held_out_sealed": True,
        "training_authorized": True,
        "model_compute_authorized": False,
        "semantic_memory_enabled": False,
        "local_ai_fallback_approved": False,
    }))
    assert hardware.main() == 1
    assert json.loads(capsys.readouterr().out)["result"] == "RX9070XT_TENSOR_SMOKE_BLOCKED"
