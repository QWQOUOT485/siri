"""Offline checks for the Laya UTF-8 launcher and fail-closed readback."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_laya_model_load_preflight as gate  # noqa: E402
from local_ai_stage_b_rx9070xt_hardware_preflight import AcceleratorDevice  # noqa: E402


def gpu(index: int, name: str, arch: str) -> AcceleratorDevice:
    return AcceleratorDevice(index, name, arch, 16_000_000_000, "cuda")


def test_child_command_uses_explicit_process_utf8_mode() -> None:
    command = gate.child_command(Path("python.exe"), Path("preflight.py"))
    assert command == ["python.exe", "-B", "-X", "utf8", "preflight.py", "--child"]
    with pytest.raises(gate.GateError, match="child_utf8_mode_missing"):
        gate.require_utf8_mode(0)


def test_target_selection_rejects_igpu_nvidia_and_ambiguity() -> None:
    integrated = gpu(0, "AMD Radeon(TM) Graphics", "gfx1036")
    target = gpu(2, "AMD Radeon RX 9070 XT", "gfx1201")
    assert gate.select_device((integrated, target)) == "cuda:2"
    for devices in ((integrated,), (target, target), (target, gpu(1, "NVIDIA RTX 3060", "sm86"))):
        with pytest.raises(Exception):
            gate.select_device(devices)


class Tensor:
    def __init__(self, device: str, *, count: int = 321_908_998) -> None:
        self.device = device
        self.dtype = "float32"
        self.requires_grad = True
        self.count = count

    def numel(self) -> int:
        return self.count


def agent(parameter_devices: tuple[str, ...], buffer_devices: tuple[str, ...], reported: str = "cuda:2"):
    model = SimpleNamespace(
        named_parameters=lambda: [(str(i), Tensor(device, count=321_908_998 if i == 0 else 0))
                                  for i, device in enumerate(parameter_devices)],
        named_buffers=lambda: [(str(i), Tensor(device, count=1)) for i, device in enumerate(buffer_devices)],
    )
    return SimpleNamespace(device=reported, model=model,
                           system_one=lambda *_: pytest.fail("forward was called"))


def test_residency_requires_exact_index_and_never_runs_forward() -> None:
    result = gate.residency(agent(("cuda:2",), ("cuda:2",)), "cuda:2")
    assert result["cpu_fallback"] is False
    assert result["parameter_count"] == 321_908_998
    assert result["trainable_parameter_count"] == 321_908_998
    for bad_agent, expected in (
        (agent(("cuda:2",), (), "cpu"), "laya_device_mismatch"),
        (agent(("cuda:0",), ()), "parameter_residency_mismatch"),
        (agent(("cuda:2", "cpu"), ()), "parameter_residency_mismatch"),
        (agent(("cuda:2",), ("cpu",)), "buffer_residency_mismatch"),
        (agent(("cuda:2",), ("cuda:0",)), "buffer_residency_mismatch"),
    ):
        with pytest.raises(gate.GateError, match=expected):
            gate.residency(bad_agent, "cuda:2")
    with pytest.raises(gate.GateError, match="selected_device_not_indexed"):
        gate.residency(agent(("cuda:2",), ()), "cuda")


def test_artifact_and_identity_changes_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = tmp_path / "tokenizer.json"
    artifact.write_bytes(b"old")
    before, _ = gate.artifact_inventory(tmp_path)
    artifact.write_bytes(b"new")
    after, _ = gate.artifact_inventory(tmp_path)
    with pytest.raises(gate.GateError, match="canonical_artifact_mutated"):
        gate.require_unchanged(before, after, "canonical_artifact_mutated")
    with pytest.raises(gate.GateError, match="package_inventory_mutated"):
        gate.require_unchanged("old", "new", "package_inventory_mutated")
    monkeypatch.setattr(gate, "_git", lambda *args: gate.SOURCE_REVISION if args[0] == "rev-parse" else " M agent.py")
    monkeypatch.setattr(gate, "SOURCE", tmp_path)
    with pytest.raises(gate.GateError, match="source_checkout_dirty"):
        gate.source_identity()


def test_wrong_weight_and_missing_model_file_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "ARTIFACT_SHA", "synthetic")
    rows = [{"path": name, "sha256": "wrong"} for name in gate.REQUIRED_MODEL_FILES]
    rows.extend({"path": str(i), "sha256": "unused"} for i in range(6))
    with pytest.raises(gate.GateError, match="primary_weight_sha_mismatch"):
        gate.model_identity(rows, "synthetic")
    rows[0]["path"] = "missing"
    with pytest.raises(gate.GateError, match="required_model_file_missing"):
        gate.model_identity(rows, "synthetic")


def test_parent_captures_raw_bytes_and_returns_bounded_blocker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "PYTHON", Path(sys.executable))
    import local_ai_stage_b_held_out_seal as seal

    monkeypatch.setattr(seal, "verify_seal", lambda: {
        "seal_manifest_sha256": gate.SEAL_SHA, "sealed_row_count": 600,
        "sealed_group_count": 100, "final_split_assigned": True,
        "held_out_sealed": True, **gate.AUTHORITY_FLAGS,
    })
    def fake_runner(command, **kwargs):
        assert command[1:4] == ["-B", "-X", "utf8"]
        assert kwargs["text"] is False
        assert kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.PIPE
        assert "universal_newlines" not in kwargs
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        payload = {"status": "LAYA_MODEL_LOAD_NEW_BLOCKER", "blocker": "RuntimeError",
                   "authority_flags": dict(gate.AUTHORITY_FLAGS)}
        return subprocess.CompletedProcess(command, 1,
            (gate.RESULT_PREFIX + json.dumps(payload) + "\n").encode(), b"non-UTF8:\xff")
    result = gate.parent(fake_runner)
    assert result["status"] == "LAYA_MODEL_LOAD_NEW_BLOCKER"
    assert result["child_returncode"] == 1
    assert all(value is False for value in result["authority_flags"].values())
