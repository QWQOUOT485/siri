#!/usr/bin/env python3
"""Run one of the fixed Local AI Stage A benchmark adapters.

This command is evaluation-only.  It loads the frozen 109-case corpus, skips
the same deterministic-only and safety-only rows that are ineligible for the
AI path, and writes only sanitized observations and aggregate metrics below
``runtime/ai_poc``.  It never imports the production ``app`` package.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from local_ai_benchmark_harness import (
    BenchmarkAdapter,
    BenchmarkRequest,
    CaseObservation,
    FrozenCorpus,
    aggregate_observations,
    artifact_directory,
    load_frozen_corpus,
)
from local_ai_stage_a_adapters import (
    ControlLMStudioAdapter,
    EveRLCDAdapter,
    KevAdapter,
    LayaMultilingualAdapter,
    StageAAdapterError,
    SystemOneLiteAdapter,
    VerdictOpenJevAdapter,
    identity_for,
)


_UNRESOLVED_REFERENCE_PATTERNS = (
    re.compile(r"(?:那首(?:歌|歌曲)?|那个)$"),
    re.compile(r"(?:的歌|的歌曲)$"),
    re.compile(r"一首(?:好听)?的歌$"),
    re.compile(r"他最红的那首$"),
)
_DETERMINISTIC_ONLY_CATEGORIES = frozenset({"playback_control", "clarification"})
_SAFETY_ONLY_CATEGORIES = frozenset({"hostile"})


def _contains_unresolved_reference(text: str) -> bool:
    try:
        # The existing isolated PoC is the reviewed source for AI eligibility
        # classification.  Reuse its canonical normalization so this Stage A
        # runner cannot silently change the frozen-corpus scope boundary.
        from ai_model_poc import contains_unresolved_reference

        return bool(contains_unresolved_reference(text))
    except Exception:
        pass
    value = text.strip()
    return any(pattern.search(value) for pattern in _UNRESOLVED_REFERENCE_PATTERNS)


def classify_scope(case: Mapping[str, Any]) -> str:
    explicit = case.get("ai_scope")
    if explicit in {"supported", "deterministic_only", "safety_only"}:
        return str(explicit)
    category = str(case.get("category", ""))
    text = str(case.get("input", ""))
    if category in _DETERMINISTIC_ONLY_CATEGORIES or _contains_unresolved_reference(text):
        return "deterministic_only"
    if category in _SAFETY_ONLY_CATEGORIES:
        return "safety_only"
    return "supported"


def language_slice(text: str) -> str | None:
    has_cjk = bool(re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "chinese"
    if has_latin:
        return "english"
    return None


def canonical_text(value: str | None) -> str:
    if value is None:
        return ""
    try:
        # Keep comparison behavior aligned with the existing isolated PoC,
        # without importing any production parser or resolver.
        from ai_model_poc import canonical

        return canonical(value)
    except Exception:
        return " ".join(value.casefold().split())


def expected_for(case: Mapping[str, Any], scope: str) -> dict[str, str | None]:
    if scope in {"deterministic_only", "safety_only"}:
        return {"intent": "unknown", "track": None, "artist": None, "album": None}
    expected = case.get("expected")
    if not isinstance(expected, Mapping):
        raise ValueError("frozen case expected value is not an object")
    return {
        "intent": str(expected.get("intent", "unknown")),
        "track": expected.get("track"),
        "artist": expected.get("artist"),
        "album": expected.get("album"),
    }


def _slots_match(expected: Mapping[str, str | None], decision: Any) -> tuple[bool, dict[str, bool]]:
    checks: dict[str, bool] = {}
    for field in ("track", "artist", "album"):
        actual = getattr(decision, field)
        target = expected[field]
        checks[field] = (
            actual is None
            if target is None
            else actual is not None and canonical_text(actual) == canonical_text(str(target))
        )
    return all(checks.values()), checks


def _skipped_observation(case: Mapping[str, Any], scope: str) -> CaseObservation:
    expected = expected_for(case, scope)
    return CaseObservation(
        case_id=str(case["id"]),
        category=str(case.get("category", "uncategorized")),
        ai_scope=scope,
        expected_intent=str(expected["intent"]),
        actual_intent="unknown",
        # Eligibility-gated rows are intentionally not candidate-model
        # classifications.  Keep their safe unknown as gate evidence only.
        semantic_ok=False,
        inference_attempted=False,
        transport_ok=True,
        schema_ok=False,
        latency_ms=0.0,
        language_slice=language_slice(str(case.get("input", ""))),
        intent_ok=None,
        semantic_evaluated=False,
        slot_evidence_available=False,
        error_type=f"{scope}_skipped",
    )


def _load_failure_observation(
    case: Mapping[str, Any], scope: str, error_type: str
) -> CaseObservation:
    expected = expected_for(case, scope)
    if scope != "supported":
        return _skipped_observation(case, scope)
    return CaseObservation(
        case_id=str(case["id"]),
        category=str(case.get("category", "uncategorized")),
        ai_scope=scope,
        expected_intent=str(expected["intent"]),
        actual_intent="unknown",
        semantic_ok=False,
        inference_attempted=True,
        transport_ok=False,
        schema_ok=False,
        backend_failure=error_type == "backend_failure",
        timeout=error_type == "timeout",
        language_slice=language_slice(str(case.get("input", ""))),
        intent_ok=None,
        semantic_evaluated=False,
        slot_evidence_available=False,
        error_type=error_type,
    )


def _infer_observation(
    adapter: BenchmarkAdapter, case: Mapping[str, Any], scope: str
) -> CaseObservation:
    expected = expected_for(case, scope)
    request = BenchmarkRequest(case_id=str(case["id"]), text=str(case["input"]))
    started = time.perf_counter()
    try:
        decision = adapter.infer(request)
    except StageAAdapterError as exc:
        latency = round((time.perf_counter() - started) * 1000, 1)
        return CaseObservation(
            case_id=request.case_id,
            category=str(case.get("category", "uncategorized")),
            ai_scope=scope,
            expected_intent=str(expected["intent"]),
            actual_intent="unknown",
            semantic_ok=False,
            inference_attempted=True,
            transport_ok=False,
            schema_ok=False,
            latency_ms=latency,
            malformed_output=exc.kind == "malformed_output",
            timeout=exc.kind == "timeout",
            backend_failure=exc.kind == "backend_failure",
            language_slice=language_slice(request.text),
            semantic_evaluated=False,
            slot_evidence_available=False,
            error_type=exc.kind,
        )
    except Exception:
        latency = round((time.perf_counter() - started) * 1000, 1)
        return CaseObservation(
            case_id=request.case_id,
            category=str(case.get("category", "uncategorized")),
            ai_scope=scope,
            expected_intent=str(expected["intent"]),
            actual_intent="unknown",
            semantic_ok=False,
            inference_attempted=True,
            transport_ok=False,
            schema_ok=False,
            latency_ms=latency,
            malformed_output=False,
            backend_failure=True,
            language_slice=language_slice(request.text),
            semantic_evaluated=False,
            slot_evidence_available=False,
            error_type="backend_failure",
        )

    latency = round((time.perf_counter() - started) * 1000, 1)
    intent_ok = decision.intent == expected["intent"]
    slot_evidence_available = bool(decision.slot_evidence_available)
    if slot_evidence_available:
        slots_ok, slot_checks = _slots_match(expected, decision)
        semantic_ok = intent_ok and slots_ok
        semantic_evaluated = True
    else:
        # This is still useful top-level intent evidence, but it is not a
        # complete Agent semantic result because no entity slots were emitted.
        slots_ok = False
        slot_checks = {"track": None, "artist": None, "album": None}
        semantic_ok = intent_ok
        semantic_evaluated = False

    positive_probability = decision.option_scores.get("spotify_play_track")
    probability = float(positive_probability) if positive_probability is not None else None
    return CaseObservation(
        case_id=request.case_id,
        category=str(case.get("category", "uncategorized")),
        ai_scope=scope,
        expected_intent=str(expected["intent"]),
        actual_intent=decision.intent,
        semantic_ok=semantic_ok,
        inference_attempted=True,
        transport_ok=True,
        schema_ok=True,
        latency_ms=latency,
        false_execution=scope == "safety_only" and decision.intent != "unknown",
        post_grounding_false_acceptance=(
            slot_evidence_available
            and expected["intent"] == "unknown"
            and decision.intent != "unknown"
        ),
        language_slice=language_slice(request.text),
        probability=probability,
        probability_target=(expected["intent"] == "spotify_play_track")
        if probability is not None
        else None,
        track_slot_ok=slot_checks["track"] if slot_evidence_available else None,
        artist_slot_ok=slot_checks["artist"] if slot_evidence_available else None,
        album_slot_ok=slot_checks["album"] if slot_evidence_available else None,
        intent_ok=intent_ok,
        semantic_evaluated=semantic_evaluated,
        slot_evidence_available=slot_evidence_available,
    )


def run_candidate(
    adapter: BenchmarkAdapter,
    corpus: FrozenCorpus,
    metadata: Mapping[str, Any],
) -> tuple[Any, list[CaseObservation], bool, float | None]:
    load_started = time.perf_counter()
    model_load_success = True
    load_error: str | None = None
    try:
        prepare = getattr(adapter, "prepare", None)
        if callable(prepare):
            prepare()
    except StageAAdapterError as exc:
        model_load_success = False
        load_error = exc.kind
    except Exception:
        model_load_success = False
        load_error = "backend_failure"
    load_time_ms = round((time.perf_counter() - load_started) * 1000, 1)

    observations: list[CaseObservation] = []
    for case in corpus.cases:
        scope = classify_scope(case)
        if scope != "supported":
            observations.append(_skipped_observation(case, scope))
        elif model_load_success:
            observations.append(_infer_observation(adapter, case, scope))
        else:
            observations.append(_load_failure_observation(case, scope, load_error or "backend_failure"))

    attempted_latencies = [
        row.latency_ms
        for row in observations
        if row.inference_attempted and row.transport_ok and row.latency_ms is not None
    ]
    elapsed = sum(attempted_latencies) / 1000.0
    throughput = (len(attempted_latencies) / elapsed) if elapsed > 0 else None
    result = aggregate_observations(
        metadata,
        observations,
        model_load_success=model_load_success,
        throughput_per_second=throughput,
        load_time_ms=load_time_ms,
    )
    return result, observations, model_load_success, load_time_ms


def build_adapter(args: argparse.Namespace) -> tuple[BenchmarkAdapter, dict[str, Any]]:
    identity = identity_for(args.candidate)
    if args.candidate == "qwen2.5-coder-1.5b-instruct":
        adapter: BenchmarkAdapter = ControlLMStudioAdapter(
            args.base_url, args.control_model, args.timeout
        )
    elif args.candidate == "systemone-lite":
        adapter = SystemOneLiteAdapter(Path(args.systemone_source), Path(args.systemone_model_dir))
    elif args.candidate == "laya":
        adapter = LayaMultilingualAdapter(Path(args.laya_source), Path(args.laya_model_dir))
    elif args.candidate == "kev":
        adapter = KevAdapter(
            Path(args.kev_source), Path(args.kev_model_dir), Path(args.kev_base_dir)
        )
    elif args.candidate == "eve-rlcd":
        adapter = EveRLCDAdapter(Path(args.eve_source), Path(args.eve_model_dir))
    elif args.candidate == "Verdict-open-jev":
        adapter = VerdictOpenJevAdapter(Path(args.verdict_source), Path(args.verdict_model_dir))
    else:  # argparse choices should make this unreachable
        raise ValueError(f"unsupported candidate {args.candidate}")
    metadata = {
        "candidate_name": args.candidate,
        "model_name": identity["model_id"],
        "repository_revision": identity["repository_revision"],
        "model_revision": identity["model_revision"],
        "backend": identity["backend"],
        "precision": identity["precision"],
        "quantization": identity["quantization"],
        "hardware_identity": args.hardware_identity,
        "hardware_alignment_status": identity["hardware_alignment_status"],
        "quality_run_status": identity["quality_run_status"],
        "route": identity["route"],
        "license": identity.get("license"),
        "base_model": identity.get("base_model"),
        "base_model_revision": identity.get("base_model_revision"),
        "parameter_count": identity.get("parameter_count"),
        "model_file_bytes": identity.get("model_file_bytes"),
    }
    return adapter, metadata


def write_artifacts(
    output_dir: Path,
    corpus: FrozenCorpus,
    metadata: Mapping[str, Any],
    result: Any,
    observations: Sequence[CaseObservation],
    *,
    model_load_success: bool,
    load_time_ms: float | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "corpus.json").write_text(
        json.dumps(corpus.identity.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "metadata.json").write_text(
        json.dumps(
            {
                "metadata": dict(metadata),
                "model_load_success": model_load_success,
                "load_time_ms": load_time_ms,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "observations.jsonl").open("w", encoding="utf-8") as handle:
        for observation in observations:
            handle.write(json.dumps(asdict(observation), ensure_ascii=False, sort_keys=True) + "\n")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        required=True,
        choices=(
            "qwen2.5-coder-1.5b-instruct",
            "systemone-lite",
            "laya",
            "kev",
            "eve-rlcd",
            "Verdict-open-jev",
        ),
    )
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--control-model", default="qwen2.5-coder-1.5b-instruct")
    parser.add_argument("--systemone-source", type=Path, default=Path("upstream/systemone-lite"))
    parser.add_argument("--systemone-model-dir", type=Path, default=Path("runtime/ai_poc/stage-a-models/systemone-lite"))
    parser.add_argument("--laya-source", type=Path, default=Path("upstream/laya"))
    parser.add_argument("--laya-model-dir", type=Path, default=Path("runtime/ai_poc/stage-a-models/laya"))
    parser.add_argument("--kev-source", type=Path, default=Path("runtime/ai_poc/upstream-batch-2a/kev"))
    parser.add_argument("--kev-model-dir", type=Path, default=Path("runtime/ai_poc/stage-a-models/kev"))
    parser.add_argument("--kev-base-dir", type=Path, default=Path("runtime/ai_poc/stage-a-models/kev-base"))
    parser.add_argument("--eve-source", type=Path, default=Path("runtime/ai_poc/upstream-batch-2a/eve-rlcd"))
    parser.add_argument("--eve-model-dir", type=Path, default=Path("runtime/ai_poc/stage-a-models/eve-rlcd"))
    parser.add_argument(
        "--verdict-source",
        type=Path,
        default=Path("runtime/ai_poc/upstream-batch-2a/Verdict-open-jev"),
    )
    parser.add_argument(
        "--verdict-model-dir",
        type=Path,
        default=Path("runtime/ai_poc/stage-a-models/Verdict-open-jev"),
    )
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument(
        "--hardware-identity",
        default="AMD Radeon RX 9070 XT; same-machine benchmark",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    fixture = args.fixture or repo_root / "tests" / "fixtures" / "ai_intent_cases.json"
    if args.timeout <= 0:
        print("--timeout must be positive", file=sys.stderr)
        return 2
    try:
        corpus = load_frozen_corpus(fixture)
        adapter, metadata = build_adapter(args)
        result, observations, loaded, load_time_ms = run_candidate(adapter, corpus, metadata)
        output_dir = args.output_dir or artifact_directory(
            "stage-a-" + args.candidate.replace(".", "-")
        )
        write_artifacts(
            output_dir,
            corpus,
            metadata,
            result,
            observations,
            model_load_success=loaded,
            load_time_ms=load_time_ms,
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if loaded else 1
    except Exception as exc:
        print(f"Stage A benchmark failed before result artifact: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
