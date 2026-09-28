"""PR90 synthetic child-result transport lab. No model or corpus imports."""

import argparse
import atexit
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


BASE = "c1a624a068beebc8c641dcd1357c526278428ac6"
PR89_SHA = "5ec4a8ae373f4cb6923e0b0fa77e55b79df6bd5b0a9767540dbbe2fdd1faa446"
PR89_RESULT_SHA = "4887b9c77210110a7b8a5311d8a5767ee858b75b1e82a34776f75d57858f3cce"
PREFIX = "LAYA_PR90_TRANSPORT="
STAGES = ("synthetic_result_built", "sanitization_started", "sanitization_completed",
          "canonical_hash_started", "canonical_hash_completed", "json_dumps_started",
          "json_dumps_completed", "stdout_write_started", "stdout_write_completed",
          "stdout_flush_completed", "atexit_completed")
SCENARIOS = tuple("ABCDEFGHIJKL")
FLAGS = {name: False for name in ("training_authorized", "model_compute_authorized",
         "semantic_memory_enabled", "local_ai_fallback_approved",
         "LOCAL_SEMANTIC_MEMORY_ENABLED", "LOCAL_AI_FALLBACK_APPROVED")}


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def payload():
    return {"schema": "synthetic-pr89-shaped-v1", "status": "SYNTHETIC_ONLY",
            "identities": {"source": "synthetic-source", "checkpoint": "synthetic-checkpoint"},
            "execution_counts": {"live_invocations": 0, "forward_batches": 0},
            "case_ids": ["synthetic-case-1"], "label_ids": [[1, 2, 0]],
            "offsets": [[[0, 2], [2, 4], [4, 5]]],
            "confusion": [[1, 0], [0, 1]], "taxonomy": {"synthetic": 1},
            "probabilities": [0.25, 0.75],
            "audit": {"allowed_reads": []},
            "process_boundary": {"raw_byte_transport": True, "synthetic": True}}


def sanitize(value):
    def walk(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if any(word in key.lower() for word in ("utterance", "token_text", "substring", "raw_path")):
                    raise ValueError("sensitive_key")
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, str) and re.search(r"[A-Za-z]:[\\/]|\\\\[^\\]", node):
            raise ValueError("absolute_path")
    walk(value)


def stage(name):
    sys.stderr.write("PR90_STAGE:" + name + "\n")
    sys.stderr.flush()


def finish_child(scenario):
    result = payload()
    stage("synthetic_result_built")
    stage("sanitization_started")
    if scenario == "B":
        result["raw_path"] = "synthetic"
    sanitize(result)
    stage("sanitization_completed")
    stage("canonical_hash_started")
    if scenario == "C":
        raise RuntimeError("synthetic_hash_failure")
    result["canonical_result_sha256"] = canonical(result)
    stage("canonical_hash_completed")
    stage("json_dumps_started")
    if scenario == "D":
        result["probabilities"] = [float("nan"), float("inf")]
    if scenario == "E":
        result["probabilities"] = [object()]
    serialized = json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False)
    stage("json_dumps_completed")
    stage("stdout_write_started")
    if scenario == "F":
        raise OSError("synthetic_stdout_write_failure")
    if scenario == "L":
        raise RuntimeError("synthetic_atexit_failure")
    if scenario == "I":
        serialized = "{malformed"
    if scenario == "J":
        result["canonical_result_sha256"] = "0" * 64
        serialized = json.dumps(result, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if scenario == "G":
        # Buffer locally: the synthetic flush failure cannot leak a valid marker.
        _ = PREFIX + serialized
        stage("stdout_write_completed")
        raise OSError("synthetic_stdout_flush_failure")
    sys.stdout.write(PREFIX + serialized + "\n")
    stage("stdout_write_completed")
    sys.stdout.flush()
    stage("stdout_flush_completed")
    if scenario == "H":
        sys.stdout.write(PREFIX + serialized + "\n")
        sys.stdout.flush()
    stage("atexit_completed")


def classify(returncode, stdout, stderr):
    try:
        out = stdout.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return "STDOUT_DECODE_ERROR"
    markers = [line[len(PREFIX):] for line in out.splitlines() if line.startswith(PREFIX)]
    if not markers:
        if returncode:
            return "NO_MARKER_NONZERO_EXIT"
        if b"Exception ignored in atexit callback" in stderr:
            return "NO_MARKER_RC0_WITH_ATEXIT_ERROR"
        return "NO_MARKER_RC0_NO_STDERR" if not stderr else "OTHER_TRANSPORT_FAILURE"
    if len(markers) != 1:
        return "DUPLICATE_MARKER"
    try:
        value = json.loads(markers[0])
    except (json.JSONDecodeError, UnicodeError):
        return "MALFORMED_JSON"
    if not isinstance(value, dict) or not isinstance(value.get("canonical_result_sha256"), str):
        return "CHILD_SCHEMA_INVALID"
    digest = value.pop("canonical_result_sha256")
    try:
        if digest != canonical(value):
            return "BAD_CANONICAL_HASH"
    except (TypeError, ValueError):
        return "CHILD_SCHEMA_INVALID"
    if value.get("schema") != "synthetic-pr89-shaped-v1" or value.get("status") != "SYNTHETIC_ONLY":
        return "CHILD_SCHEMA_INVALID"
    return "TRANSPORT_OK" if returncode == 0 else "OTHER_TRANSPORT_FAILURE"


def evidence_row(scenario, completed):
    stderr = completed.stderr.decode("utf-8", "replace")
    trace = re.findall(r"^PR90_STAGE:([a-z_]+)\r?$", stderr, re.M)
    classes = re.findall(r"^(ValueError|RuntimeError|TypeError|OSError): ([^\r\n]+)\r?$", stderr, re.M)
    exception_class, message = classes[-1] if classes else (None, None)
    # Only allow fixed synthetic message tokens; no traceback/path is persisted.
    safe_messages = ("sensitive_key", "Out of range float values are not JSON compliant",
                     "Object of type object is not JSON serializable")
    if message and not message.startswith("synthetic_") and message not in safe_messages:
        message = "redacted"
    return {"scenario": scenario, "returncode": completed.returncode,
            "stdout_bytes": len(completed.stdout), "stderr_bytes": len(completed.stderr),
            "stdout_marker_count": sum(line.startswith(PREFIX.encode()) for line in completed.stdout.splitlines()),
            "stage_trace": trace, "last_completed_stage": trace[-1] if trace else None,
            "stderr_exception_class": exception_class,
            "stderr_exception_message": message,
            "classifier": classify(completed.returncode, completed.stdout, completed.stderr)}


def static_binding(root):
    path = root / "scripts/local_ai_stage_b_laya_span_typed_diagnosis.py"
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == PR89_SHA, "PR89 source drift"
    start = source.index("def finish_child(")
    end = source.index("\ndef scratch_inventory", start)
    body = source[start:end]
    operations = ("sanitization_check(result)", "canonical_hash(result)", "print(PREFIX + json.dumps(")
    assert all(item in body for item in operations)
    assert [body.index(item) for item in operations] == sorted(body.index(item) for item in operations)
    assert "atexit.register(lambda: finish_child(*holder) if holder else None)" in source
    assert "stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False" in source
    parent = source[source.index("def parent("):source.index("\ndef main()", source.index("def parent("))]
    assert "completed.stderr" not in parent
    return {"runner_sha256": digest, "atexit_register": True, "finish_child_order": list(operations),
            "parent_stderr_pipe": True, "parent_stderr_durably_retained": False}


def run(root):
    binding = static_binding(root)
    rows = []
    for scenario in SCENARIOS:
        child = subprocess.run([sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                                "--child", scenario], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               check=False, timeout=30)
        rows.append(evidence_row(scenario, child))
    reproduced = rows[-1]["classifier"] == "NO_MARKER_RC0_WITH_ATEXIT_ERROR"
    expected = ["TRANSPORT_OK"] + ["NO_MARKER_RC0_WITH_ATEXIT_ERROR"] * 6 + [
        "DUPLICATE_MARKER", "MALFORMED_JSON", "BAD_CANONICAL_HASH",
        "NO_MARKER_NONZERO_EXIT", "NO_MARKER_RC0_WITH_ATEXIT_ERROR"]
    ok = [row["classifier"] for row in rows] == expected and rows[0]["stage_trace"] == list(STAGES)
    result = {"schema": "laya-child-transport-diagnosis-v1",
              "status": "LAYA_CHILD_TRANSPORT_DIAGNOSIS_COMPLETED" if ok and reproduced else "LAYA_CHILD_TRANSPORT_DIAGNOSIS_NEW_BLOCKER",
              "repo_base": BASE, "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "pr89_runner_sha256": PR89_SHA, "pr89_blocker_canonical_sha256": PR89_RESULT_SHA,
              "authority_flags": FLAGS, "model_access": False, "checkpoint_access": False,
              "dataset_access": False, "gpu_access": False, "scenarios": rows,
              "pr89_external_symptom_reproduced": reproduced,
              "mechanism": "atexit exception can produce rc0 + no marker + stderr-only failure" if reproduced else "not reproduced",
              "pr89_exact_failing_operation": "unknown", "static_pr89_binding": binding,
              "static_candidate_audit": {"status": "STATIC_CANDIDATE_ONLY",
                 "candidates": ["Python scalar/list/dict", "possible numpy scalar", "possible tensor/object",
                                "possible non-finite float", "possible Path/object"]}}
    result["canonical_result_sha256"] = canonical(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=SCENARIOS)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    if args.child:
        if args.child == "K":
            return 7
        atexit.register(finish_child, args.child)
        return 0
    root = args.root or Path(__file__).resolve().parents[1]
    print(json.dumps(run(root), sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
