from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import local_ai_benchmark_harness as harness  # noqa: E402
import local_ai_benchmark_manifest as manifest  # noqa: E402
import local_ai_benchmark_preflight as preflight  # noqa: E402


def _observation(
    case_id: str,
    *,
    category: str = "basic_playback",
    ai_scope: str = "supported",
    expected_intent: str = "spotify_play_track",
    actual_intent: str = "spotify_play_track",
    semantic_ok: bool = True,
    inference_attempted: bool = True,
    transport_ok: bool = True,
    schema_ok: bool = True,
    **kwargs,
) -> harness.CaseObservation:
    return harness.CaseObservation(
        case_id=case_id,
        category=category,
        ai_scope=ai_scope,
        expected_intent=expected_intent,
        actual_intent=actual_intent,
        semantic_ok=semantic_ok,
        inference_attempted=inference_attempted,
        transport_ok=transport_ok,
        schema_ok=schema_ok,
        **kwargs,
    )


def _metadata(route: str = harness.AdapterRoute.ENCODER_CLASSIFICATION.value) -> dict[str, str]:
    return {
        "candidate_name": "candidate",
        "model_name": "model",
        "repository_revision": "repo-sha",
        "model_revision": "model-sha",
        "backend": "rocm",
        "precision": "fp16",
        "quantization": "none",
        "hardware_identity": "RX 9070 XT",
        "hardware_alignment_status": "RX_9070_XT_BACKEND_USED",
        "quality_run_status": "aligned GPU quality run completed",
        "route": route,
    }


def test_manifest_keeps_the_reviewed_fixed_candidate_set():
    candidates = manifest.candidate_manifest()

    assert tuple(item.candidate_name for item in candidates) == (
        "systemone-lite",
        "kev",
        "eve-rlcd",
        "decider",
        "system-one-open",
        "laya",
        "Verdict-open-jev",
        "open-jev-deberta-v3-large",
    )
    manifest.validate_fixed_candidate_set(candidates)
    assert manifest.candidate_manifest(include_optional=True)[-1].candidate_name == "LitJev"


def test_frozen_corpus_identity_and_drift_detection(tmp_path):
    identity = harness.compute_corpus_identity()
    assert identity.case_count == 109
    assert identity.sha256 == harness.FROZEN_CORPUS_SHA256
    corpus = harness.load_frozen_corpus()
    assert corpus.identity == identity
    assert len(corpus.cases) == 109

    changed = json.loads(harness.DEFAULT_CORPUS_PATH.read_text(encoding="utf-8"))
    changed[0]["input"] += " changed"
    changed_path = tmp_path / "changed.json"
    changed_path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(harness.CorpusDriftError, match="hash changed"):
        harness.load_frozen_corpus(
            changed_path,
            expected_case_count=109,
            expected_sha256=harness.FROZEN_CORPUS_SHA256,
        )


def test_benchmark_decision_and_adapter_reject_authority_and_invalid_slots():
    adapter = harness.CallableBenchmarkAdapter(
        harness.AdapterRoute.AUTOREGRESSIVE_STRICT_SCHEMA,
        "test-model",
        lambda _request: {"intent": "spotify_play_track", "track": "晴天"},
    )
    decision = adapter.infer(harness.BenchmarkRequest("case-1", "播放晴天"))
    assert decision.intent == "spotify_play_track"
    assert decision.track == "晴天"
    assert not hasattr(decision, "action")

    with pytest.raises(harness.BenchmarkSchemaError, match="requires a track"):
        harness.BenchmarkDecision(intent="spotify_play_track")
    with pytest.raises(harness.BenchmarkSchemaError, match="authority"):
        harness.BenchmarkDecision.from_mapping(
            {"intent": "unknown", "track": None, "shell": "shutdown /s"}
        )
    with pytest.raises(harness.BenchmarkSchemaError, match="authority"):
        harness.CallableBenchmarkAdapter(
            harness.AdapterRoute.ENCODER_CLASSIFICATION,
            "bad-model",
            lambda _request: {"intent": "unknown", "track": None, "url": "https://example.invalid"},
        ).infer(harness.BenchmarkRequest("case-2", "不相關"))


def test_result_schema_rejects_missing_unknown_and_authority_fields():
    observation = _observation("case-1", latency_ms=10.0)
    result = harness.aggregate_observations(
        _metadata(),
        [observation],
        model_load_success=True,
    )
    assert harness.BenchmarkResult.from_mapping(result.to_dict()) == result

    missing = result.to_dict()
    del missing["backend"]
    with pytest.raises(harness.BenchmarkSchemaError, match="missing fields"):
        harness.BenchmarkResult.from_mapping(missing)

    forbidden = result.to_dict()
    forbidden["shell"] = "cmd /c shutdown /s"
    with pytest.raises(harness.BenchmarkSchemaError, match="authority"):
        harness.BenchmarkResult.from_mapping(forbidden)

    with pytest.raises(harness.BenchmarkSchemaError, match="unique case IDs"):
        harness.aggregate_observations(
            _metadata(),
            [observation, observation],
            model_load_success=True,
        )


def test_result_schema_validates_intent_accuracy_rate_fields():
    result = harness.aggregate_observations(
        _metadata(),
        [_observation("case-1", category="semantic_retry")],
        model_load_success=True,
    )

    for field_name, invalid_value in (
        ("supported_intent_accuracy", "invalid"),
        ("supported_intent_accuracy", 1.1),
        ("supported_intent_accuracy", True),
        ("semantic_retry_intent_accuracy", -0.1),
        ("semantic_retry_intent_accuracy", "invalid"),
        ("semantic_retry_intent_accuracy", float("nan")),
        ("semantic_retry_intent_accuracy", float("inf")),
    ):
        payload = result.to_dict()
        payload[field_name] = invalid_value
        with pytest.raises(harness.BenchmarkSchemaError, match=field_name):
            harness.BenchmarkResult.from_mapping(payload)

    valid_payload = result.to_dict()
    valid_payload["supported_intent_accuracy"] = None
    valid_payload["semantic_retry_intent_accuracy"] = 1.0
    restored = harness.BenchmarkResult.from_mapping(valid_payload)
    assert restored.supported_intent_accuracy is None
    assert restored.semantic_retry_intent_accuracy == 1.0


def test_aggregate_records_safety_language_slots_calibration_and_failures():
    observations = [
        _observation(
            "zh",
            language_slice="chinese",
            probability=0.9,
            probability_target=True,
            latency_ms=10.0,
            track_slot_ok=True,
            artist_slot_ok=True,
        ),
        _observation(
            "en",
            language_slice="english",
            semantic_ok=False,
            schema_ok=False,
            malformed_output=True,
            probability=0.2,
            probability_target=False,
            latency_ms=30.0,
            track_slot_ok=False,
            error_type="malformed_output",
        ),
        _observation(
            "mixed-retry",
            category="semantic_retry",
            language_slice="mixed",
            probability=0.8,
            probability_target=True,
            latency_ms=20.0,
            option_order_flipped=True,
            track_slot_ok=True,
            error_type="retry",
        ),
        _observation(
            "deterministic",
            category="playback_control",
            ai_scope="deterministic_only",
            expected_intent="unknown",
            actual_intent="unknown",
            inference_attempted=False,
            transport_ok=False,
            schema_ok=False,
        ),
        _observation(
            "safety",
            category="hostile",
            ai_scope="safety_only",
            expected_intent="unknown",
            actual_intent="unknown",
            inference_attempted=False,
            transport_ok=False,
            schema_ok=False,
        ),
        _observation(
            "false-execution",
            semantic_ok=True,
            false_execution=True,
            post_grounding_false_acceptance=True,
            error_type="backend_failure",
        ),
    ]
    result = harness.aggregate_observations(
        _metadata(harness.AdapterRoute.DECODER_OPTION_SCORING.value),
        observations,
        model_load_success=True,
        throughput_per_second=12.5,
        peak_vram_bytes=16 * 1024**3,
        peak_system_ram_bytes=32 * 1024**3,
        load_time_ms=123.4,
    )

    assert result.case_count == 6
    assert result.transport_success_rate == 1.0
    assert result.typed_output_schema_success_rate == 0.75
    assert result.supported_semantic_accuracy == 0.75
    assert result.semantic_retry_accuracy == 1.0
    assert result.deterministic_only_eligibility_gate_safe_unknown_rate == 1.0
    assert result.safety_only_eligibility_gate_safe_unknown_rate == 1.0
    assert result.false_execution_rate == 0.1667
    assert result.post_grounding_false_acceptance_rate == 0.25
    assert result.p50_latency_ms == 20.0
    assert result.p95_latency_ms == 29.0
    assert result.brier_score == 0.03
    assert result.expected_calibration_error == 0.1667
    assert result.option_order_flip_rate == 1.0
    assert result.language_slice_accuracy == {"chinese": 1.0, "english": 0.0, "mixed": 1.0}
    assert result.slot_accuracy == {"artist": 1.0, "track": 0.6667}
    assert result.error_counts == {"backend_failure": 1, "malformed_output": 1, "retry": 1}


def test_aggregate_class_metrics_use_supported_expected_class_denominators():
    observations = [
        *(
            _observation(
                f"play-{index}",
                expected_intent="spotify_play_track",
                actual_intent="spotify_play_track",
                intent_ok=True,
                semantic_evaluated=False,
                slot_evidence_available=False,
            )
            for index in range(57)
        ),
        *(
            _observation(
                f"unknown-{index}",
                expected_intent="unknown",
                actual_intent="spotify_play_track",
                intent_ok=False,
                semantic_evaluated=False,
                slot_evidence_available=False,
                # This mirrors the old raw observation flag.  The route did
                # not emit slots, so it must not become post-grounding data.
                post_grounding_false_acceptance=True,
            )
            for index in range(6)
        ),
        *(
            _observation(
                f"deterministic-{index}",
                category="playback_control",
                ai_scope="deterministic_only",
                expected_intent="unknown",
                actual_intent="unknown",
                semantic_ok=False,
                inference_attempted=False,
                transport_ok=True,
                schema_ok=False,
                intent_ok=None,
                semantic_evaluated=False,
                slot_evidence_available=False,
            )
            for index in range(36)
        ),
        *(
            _observation(
                f"safety-{index}",
                category="hostile",
                ai_scope="safety_only",
                expected_intent="unknown",
                actual_intent="unknown",
                semantic_ok=False,
                inference_attempted=False,
                transport_ok=True,
                schema_ok=False,
                intent_ok=None,
                semantic_evaluated=False,
                slot_evidence_available=False,
            )
            for index in range(10)
        ),
    ]

    result = harness.aggregate_observations(
        _metadata(harness.AdapterRoute.DECODER_OPTION_SCORING.value),
        observations,
        model_load_success=True,
    )

    assert result.case_count == 109
    assert result.supported_case_count == 63
    assert result.candidate_model_evaluated_supported_case_count == 63
    assert result.supported_expected_play_case_count == 57
    assert result.supported_expected_unknown_case_count == 6
    assert result.play_true_positive_count == 57
    assert result.play_recall == 1.0
    assert result.unknown_true_negative_count == 0
    assert result.unknown_recall == 0.0
    assert result.balanced_intent_accuracy == 0.5
    assert result.supported_intent_accuracy == 0.9048
    assert result.expected_unknown_false_accept_count == 6
    assert result.expected_unknown_false_accept_rate == 1.0
    assert result.expected_unknown_false_acceptance_incidence_rate == 0.055
    assert result.post_grounding_false_acceptance_rate is None
    assert result.entity_slot_evaluation_available is False
    assert result.deterministic_only_cases_not_sent_to_model == 36
    assert result.safety_only_cases_not_sent_to_model == 10
    assert result.deterministic_only_eligibility_gate_safe_unknown_rate == 1.0
    assert result.safety_only_eligibility_gate_safe_unknown_rate == 1.0


def test_full_semantic_control_stays_distinct_from_typed_intent_only():
    control = harness.aggregate_observations(
        _metadata(harness.AdapterRoute.AUTOREGRESSIVE_STRICT_SCHEMA.value),
        [
            _observation(
                "control-play",
                intent_ok=True,
                semantic_ok=True,
                track_slot_ok=True,
                artist_slot_ok=True,
            ),
            _observation(
                "control-unknown",
                expected_intent="unknown",
                actual_intent="unknown",
                intent_ok=True,
                semantic_ok=True,
                track_slot_ok=True,
                artist_slot_ok=True,
            ),
        ],
        model_load_success=True,
    )
    typed = harness.aggregate_observations(
        _metadata(harness.AdapterRoute.DECODER_OPTION_SCORING.value),
        [
            _observation(
                "typed-play",
                intent_ok=True,
                semantic_ok=True,
                semantic_evaluated=False,
                slot_evidence_available=False,
            ),
            _observation(
                "typed-unknown",
                expected_intent="unknown",
                actual_intent="unknown",
                intent_ok=True,
                semantic_ok=True,
                semantic_evaluated=False,
                slot_evidence_available=False,
            ),
        ],
        model_load_success=True,
    )

    assert control.supported_semantic_accuracy == 1.0
    assert control.supported_intent_accuracy == 1.0
    assert control.entity_slot_evaluation_available is True
    assert control.post_grounding_false_acceptance_rate == 0.0
    assert typed.supported_semantic_accuracy is None
    assert typed.supported_intent_accuracy == 1.0
    assert typed.entity_slot_evaluation_available is False
    assert typed.post_grounding_false_acceptance_rate is None


def test_preflight_missing_tools_does_not_execute_any_command():
    report = preflight.collect_preflight(which=lambda _name: None, runner=lambda *_args, **_kwargs: pytest.fail("ran"))

    assert all(not probe.available for probe in report.probes)
    assert report.gpu_match is None
    assert report.vram_bytes is None
    assert report.vram_source == "unknown"
    assert report.benchmark_execution == "not_attempted"
    assert report.model_weight_access == "not_attempted"
    assert report.backend_availability == {
        "amd_smi": False,
        "rocm": False,
        "vulkan": False,
        "opencl": False,
        "directml_package": report.python_packages["onnxruntime-directml"] is not None,
    }


def test_preflight_uses_only_fixed_no_shell_commands_and_parses_gpu_inventory():
    calls: list[dict[str, object]] = []

    def fake_runner(command, **kwargs):
        calls.append({"command": command, **kwargs})
        if command[0].endswith("powershell.exe"):
            stdout = json.dumps(
                [
                    {
                        "Name": "AMD Radeon RX 9070 XT",
                        "DriverVersion": "1.2.3",
                        "AdapterRAM": 16 * 1024**3,
                    },
                    {
                        "Name": "AMD Radeon(TM) Graphics",
                        "DriverVersion": "1.2.3",
                        "AdapterRAM": 64 * 1024**3,
                    },
                ]
            )
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    report = preflight.collect_preflight(
        which=lambda name: f"C:\\tools\\{name}",
        runner=fake_runner,
    )

    assert report.gpu_names == ("AMD Radeon RX 9070 XT", "AMD Radeon(TM) Graphics")
    assert report.gpu_match is True
    assert report.vram_bytes == 16 * 1024**3
    assert report.vram_source == "wmi"
    assert len(calls) == len(preflight.COMMAND_SPECS)
    assert all(call["shell"] is False for call in calls)
    assert all(call["timeout"] == preflight.DEFAULT_COMMAND_TIMEOUT_SECONDS for call in calls)
    assert all(isinstance(call["command"], list) for call in calls)
    assert all(not any("cmd /c" in str(part).lower() for part in call["command"]) for call in calls)
    clinfo_spec = next(spec for spec in preflight.COMMAND_SPECS if spec.name == "clinfo")
    assert clinfo_spec.arguments == ()
    assert all("-l" not in call["command"] for call in calls)


def test_preflight_timeout_is_reported_without_raising():
    def timeout_runner(command, **_kwargs):
        raise subprocess.TimeoutExpired(command, 1, output=b"partial", stderr=b"timed out")

    probe = preflight.run_probe(
        preflight.COMMAND_SPECS[0],
        which=lambda _name: "powershell.exe",
        runner=timeout_runner,
    )

    assert probe.available is True
    assert probe.timed_out is True
    assert probe.return_code is None
    assert probe.stdout == "partial"
    assert probe.stderr == "timed out"


def test_preflight_rejects_commands_outside_the_fixed_probe_set():
    with pytest.raises(ValueError, match="fixed preflight command set"):
        preflight.run_probe(
            preflight.CommandSpec("arbitrary", ("cmd.exe",), ("/c", "whoami"), "unsafe"),
            which=lambda _name: "cmd.exe",
            runner=lambda *_args, **_kwargs: pytest.fail("ran"),
        )


def test_preflight_prefers_discrete_gpu_memory_when_wmi_is_truncated():
    probes = (
        preflight.CommandProbe(
            name="windows_gpu_inventory",
            category="gpu_driver",
            executable="powershell.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout=json.dumps(
                [
                    {"Name": "AMD Radeon RX 9070 XT", "AdapterRAM": 4_293_918_720},
                    {"Name": "AMD Radeon(TM) Graphics", "AdapterRAM": 536_870_912},
                ]
            ),
            stderr="",
        ),
        preflight.CommandProbe(
            name="clinfo",
            category="opencl",
            executable="clinfo.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout=(
                "Board name: AMD Radeon RX 9070 XT\n"
                "Global memory size: 17095983104\n"
                "Board name: AMD Radeon(TM) Graphics\n"
                "Global memory size: 13064830976\n"
            ),
            stderr="",
        ),
    )

    assert preflight._extract_vram_evidence(probes) == (17_095_983_104, "opencl")


def test_preflight_list_only_opencl_output_cannot_produce_vram():
    probes = (
        preflight.CommandProbe(
            name="windows_gpu_inventory",
            category="gpu_driver",
            executable="powershell.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout=json.dumps(
                [
                    {"Name": "AMD Radeon RX 9070 XT", "AdapterRAM": 4_293_918_720},
                    {"Name": "AMD Radeon(TM) Graphics", "AdapterRAM": 64 * 1024**3},
                ]
            ),
            stderr="",
        ),
        preflight.CommandProbe(
            name="clinfo",
            category="opencl",
            executable="clinfo.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout="Platform Name: AMD Accelerated Parallel Processing\nBoard name: AMD Radeon RX 9070 XT\n",
            stderr="",
        ),
    )

    assert preflight._extract_vram_evidence(probes) == (None, "unknown")


def test_preflight_accepts_target_specific_opencl_memory_over_larger_integrated_memory():
    probes = (
        preflight.CommandProbe(
            name="windows_gpu_inventory",
            category="gpu_driver",
            executable="powershell.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout=json.dumps(
                [
                    {"Name": "AMD Radeon RX 9070 XT", "AdapterRAM": 4_293_918_720},
                    {"Name": "AMD Radeon(TM) Graphics", "AdapterRAM": 64 * 1024**3},
                ]
            ),
            stderr="",
        ),
        preflight.CommandProbe(
            name="clinfo",
            category="opencl",
            executable="clinfo.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout=(
                "Board name: AMD Radeon(TM) Graphics\n"
                "Global memory size: 68719476736\n"
                "Board name: AMD Radeon RX 9070 XT\n"
                "Global memory size: 17095983104\n"
            ),
            stderr="",
        ),
    )

    assert preflight._extract_vram_evidence(probes) == (17_095_983_104, "opencl")


def test_preflight_unreliable_wmi_without_target_secondary_fails_closed():
    probes = (
        preflight.CommandProbe(
            name="windows_gpu_inventory",
            category="gpu_driver",
            executable="powershell.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout=json.dumps(
                [
                    {"Name": "AMD Radeon RX 9070 XT", "AdapterRAM": 4_293_918_720},
                    {"Name": "AMD Radeon(TM) Graphics", "AdapterRAM": 128 * 1024**3},
                ]
            ),
            stderr="",
        ),
        preflight.CommandProbe(
            name="clinfo",
            category="opencl",
            executable="clinfo.exe",
            available=True,
            return_code=0,
            timed_out=False,
            stdout="Platform Name: AMD Accelerated Parallel Processing\n",
            stderr="",
        ),
    )

    assert preflight._extract_vram_evidence(probes) == (None, "unknown")
