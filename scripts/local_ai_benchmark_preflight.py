#!/usr/bin/env python3
"""Read-only environment preflight for the Local AI benchmark.

The preflight records whether the reviewed RX 9070 XT environment appears to
have usable GPU/runtime tooling.  It does not import the application, resolve
models, access model weights, download anything, start a server, or run a
benchmark.  Every external command is fixed below and runs without a shell.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Sequence


EXPECTED_GPU_NAME = "AMD Radeon RX 9070 XT"
MAX_PROBE_OUTPUT_CHARS = 12_000
DEFAULT_COMMAND_TIMEOUT_SECONDS = 8.0
_TARGET_GPU_PATTERN = re.compile(r"\brx\s*9070\s*xt\b", re.IGNORECASE)
_WMI_UINT32_MAX = 0xFFFFFFFF


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """A fixed local command; no user text is interpolated into it."""

    name: str
    executables: tuple[str, ...]
    arguments: tuple[str, ...]
    category: str


@dataclass(frozen=True, slots=True)
class CommandProbe:
    name: str
    category: str
    executable: str | None
    available: bool
    return_code: int | None
    timed_out: bool
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PreflightReport:
    generated_by: str
    python_executable: str
    python_version: str
    platform: str
    expected_gpu: str
    gpu_names: tuple[str, ...]
    gpu_match: bool | None
    vram_bytes: int | None
    vram_source: str
    python_packages: Mapping[str, str | None]
    backend_availability: Mapping[str, bool]
    probes: tuple[CommandProbe, ...]
    benchmark_execution: str
    model_weight_access: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gpu_names"] = list(self.gpu_names)
        payload["python_packages"] = dict(self.python_packages)
        payload["backend_availability"] = dict(self.backend_availability)
        payload["probes"] = [probe.to_dict() for probe in self.probes]
        return payload


# Keep this list explicit.  A preflight must not accept an arbitrary command
# or package name from a caller and then pass it to subprocess/import machinery.
COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        name="windows_gpu_inventory",
        executables=("powershell.exe", "pwsh.exe"),
        arguments=(
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "$ErrorActionPreference='Stop'; "
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name,DriverVersion,AdapterRAM | "
                "ConvertTo-Json -Compress"
            ),
        ),
        category="gpu_driver",
    ),
    CommandSpec(
        name="amd_smi",
        executables=("amd-smi.exe", "amd-smi"),
        arguments=("list",),
        category="amd_driver",
    ),
    CommandSpec(
        name="rocm_smi",
        executables=("rocm-smi.exe", "rocm-smi"),
        arguments=("--showproductname", "--showdriverversion", "--showmeminfo", "vram"),
        category="rocm",
    ),
    CommandSpec(
        name="rocminfo",
        executables=("rocminfo.exe", "rocminfo"),
        arguments=(),
        category="rocm",
    ),
    CommandSpec(
        name="hipconfig",
        executables=("hipconfig.exe", "hipconfig"),
        arguments=("--version",),
        category="rocm",
    ),
    CommandSpec(
        name="vulkaninfo",
        executables=("vulkaninfo.exe", "vulkaninfo"),
        arguments=("--summary",),
        category="vulkan",
    ),
    CommandSpec(
        name="clinfo",
        executables=("clinfo.exe", "clinfo"),
        # The default clinfo mode emits per-device properties, including
        # Global memory size.  ``clinfo -l`` is list-only on supported builds
        # and is deliberately not used for VRAM evidence.
        arguments=(),
        category="opencl",
    ),
)

PACKAGE_NAMES: tuple[str, ...] = (
    "torch",
    "transformers",
    "onnxruntime",
    "onnxruntime-directml",
    "llama-cpp-python",
    "openvino",
    "vllm",
)

Runner = Callable[..., subprocess.CompletedProcess[str]]
Which = Callable[[str], str | None]


def _bounded(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    value = value.replace("\x00", "")
    if len(value) <= MAX_PROBE_OUTPUT_CHARS:
        return value
    return value[:MAX_PROBE_OUTPUT_CHARS] + "\n...[truncated]"


def _resolve_executable(spec: CommandSpec, which: Which) -> str | None:
    for name in spec.executables:
        resolved = which(name)
        if resolved:
            return resolved
    return None


def run_probe(
    spec: CommandSpec,
    *,
    timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    which: Which = shutil.which,
    runner: Runner = subprocess.run,
) -> CommandProbe:
    """Run one fixed, bounded, local probe without invoking a shell."""

    if spec not in COMMAND_SPECS:
        raise ValueError("probe is not in the fixed preflight command set")
    executable = _resolve_executable(spec, which)
    if executable is None:
        return CommandProbe(
            name=spec.name,
            category=spec.category,
            executable=None,
            available=False,
            return_code=None,
            timed_out=False,
            stdout="",
            stderr="not found",
        )
    try:
        completed = runner(
            [executable, *spec.arguments],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandProbe(
            name=spec.name,
            category=spec.category,
            executable=executable,
            available=True,
            return_code=None,
            timed_out=True,
            stdout=_bounded(exc.stdout),
            stderr=_bounded(exc.stderr),
        )
    except OSError as exc:
        return CommandProbe(
            name=spec.name,
            category=spec.category,
            executable=executable,
            available=True,
            return_code=None,
            timed_out=False,
            stdout="",
            stderr=_bounded(str(exc)),
        )
    return CommandProbe(
        name=spec.name,
        category=spec.category,
        executable=executable,
        available=True,
        return_code=completed.returncode,
        timed_out=False,
        stdout=_bounded(completed.stdout),
        stderr=_bounded(completed.stderr),
    )


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGE_NAMES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _json_records(output: str) -> list[Mapping[str, Any]]:
    if not output.strip():
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, Mapping):
        payload = [payload]
    if not isinstance(payload, list):
        return []
    return [record for record in payload if isinstance(record, Mapping)]


def _gpu_names(probes: Sequence[CommandProbe]) -> tuple[str, ...]:
    names: list[str] = []
    inventory = next((probe for probe in probes if probe.name == "windows_gpu_inventory"), None)
    if inventory is not None:
        for record in _json_records(inventory.stdout):
            name = record.get("Name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    for probe in probes:
        if probe.name in {"amd_smi", "rocm_smi", "rocminfo"}:
            for line in probe.stdout.splitlines():
                if re.search(r"(?:Radeon|RX\s+\d{3,4}|gfx\d+)", line, re.IGNORECASE):
                    cleaned = line.strip()
                    if cleaned:
                        names.append(cleaned)
    return tuple(dict.fromkeys(names))


def _is_target_gpu_name(value: Any) -> bool:
    return isinstance(value, str) and bool(_TARGET_GPU_PATTERN.search(value))


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    value = int(value)
    return value if value > 0 else None


def _wmi_target_vram_bytes(probes: Sequence[CommandProbe]) -> int | None:
    """Return only a reliable AdapterRAM value attached to the target name.

    Win32_VideoController.AdapterRAM is commonly exposed as a 32-bit field.
    A value within that range cannot reliably describe this 16-GiB-class
    target, so it is rejected rather than treated as an inferred capacity.
    """

    target_values: list[int] = []
    inventory = next((probe for probe in probes if probe.name == "windows_gpu_inventory"), None)
    if inventory is None:
        return None
    for record in _json_records(inventory.stdout):
        if not _is_target_gpu_name(record.get("Name")):
            continue
        value = _positive_integer(record.get("AdapterRAM"))
        if value is not None and value > _WMI_UINT32_MAX:
            target_values.append(value)
    if target_values and len(set(target_values)) == 1:
        return target_values[0]
    return None


def _opencl_target_vram_bytes(probes: Sequence[CommandProbe]) -> int | None:
    """Parse Global memory size only from a target-named clinfo device block."""

    block_pattern = re.compile(
        r"^\s*(?:Board name|Device name|deviceName)\s*[:=]\s*(?P<name>[^\r\n]+)"
        r"(?P<body>.*?)(?=^\s*(?:Board name|Device name|deviceName)\s*[:=]|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    target_values: list[int] = []
    for probe in probes:
        if probe.name != "clinfo":
            continue
        for match in block_pattern.finditer(probe.stdout):
            if not _is_target_gpu_name(match.group("name")):
                continue
            memory_values = [
                int(raw)
                for raw in re.findall(
                    r"^\s*Global memory size\s*:\s*(\d+)\s*$",
                    match.group("body"),
                    re.IGNORECASE | re.MULTILINE,
                )
            ]
            if len(memory_values) == 1 and memory_values[0] > 0:
                target_values.append(memory_values[0])
    if target_values and len(set(target_values)) == 1:
        return target_values[0]
    return None


def _extract_vram_evidence(probes: Sequence[CommandProbe]) -> tuple[int | None, str]:
    wmi_value = _wmi_target_vram_bytes(probes)
    if wmi_value is not None:
        return wmi_value, "wmi"
    opencl_value = _opencl_target_vram_bytes(probes)
    if opencl_value is not None:
        return opencl_value, "opencl"
    return None, "unknown"


def _extract_vram_bytes(probes: Sequence[CommandProbe]) -> int | None:
    """Compatibility helper returning only the target-specific byte value."""

    return _extract_vram_evidence(probes)[0]


def _backend_availability(
    probes: Sequence[CommandProbe], packages: Mapping[str, str | None]
) -> dict[str, bool]:
    successful = {probe.name for probe in probes if probe.available and probe.return_code == 0 and not probe.timed_out}
    return {
        "amd_smi": "amd_smi" in successful,
        "rocm": bool(successful & {"rocm_smi", "rocminfo", "hipconfig"}),
        "vulkan": "vulkaninfo" in successful,
        "opencl": "clinfo" in successful,
        "directml_package": packages.get("onnxruntime-directml") is not None,
    }


def collect_preflight(
    *,
    timeout_seconds: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    which: Which = shutil.which,
    runner: Runner = subprocess.run,
) -> PreflightReport:
    """Collect environment facts only; no model or application is touched."""

    probes = tuple(
        run_probe(spec, timeout_seconds=timeout_seconds, which=which, runner=runner)
        for spec in COMMAND_SPECS
    )
    names = _gpu_names(probes)
    gpu_match: bool | None = None if not names else any(_is_target_gpu_name(name) for name in names)
    vram_bytes, vram_source = _extract_vram_evidence(probes)
    packages = _package_versions()
    return PreflightReport(
        generated_by="local_ai_benchmark_preflight",
        python_executable=sys.executable,
        python_version=platform.python_version(),
        platform=platform.platform(),
        expected_gpu=EXPECTED_GPU_NAME,
        gpu_names=names,
        gpu_match=gpu_match,
        vram_bytes=vram_bytes,
        vram_source=vram_source,
        python_packages=packages,
        backend_availability=_backend_availability(probes, packages),
        probes=probes,
        benchmark_execution="not_attempted",
        model_weight_access="not_attempted",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_COMMAND_TIMEOUT_SECONDS,
        help="per-probe timeout; this does not change the fixed commands",
    )
    args = parser.parse_args(argv)
    if not 0.1 <= args.timeout_seconds <= 60.0:
        parser.error("--timeout-seconds must be between 0.1 and 60")
    report = collect_preflight(timeout_seconds=args.timeout_seconds)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
