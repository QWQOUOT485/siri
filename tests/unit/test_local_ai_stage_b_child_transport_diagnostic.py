"""CPU-only checks for the PR90 synthetic subprocess lab."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/local_ai_stage_b_child_transport_diagnostic.py"
spec = importlib.util.spec_from_file_location("pr90_transport", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_synthetic_matrix_and_stages():
    result = mod.run(ROOT)
    assert result["status"] == "LAYA_CHILD_TRANSPORT_DIAGNOSIS_COMPLETED"
    assert result["pr89_external_symptom_reproduced"] is True
    rows = result["scenarios"]
    assert [r["scenario"] for r in rows] == list("ABCDEFGHIJKL")
    assert [r["classifier"] for r in rows] == ["TRANSPORT_OK"] + [
        "NO_MARKER_RC0_WITH_ATEXIT_ERROR"] * 6 + ["DUPLICATE_MARKER", "MALFORMED_JSON",
        "BAD_CANONICAL_HASH", "NO_MARKER_NONZERO_EXIT", "NO_MARKER_RC0_WITH_ATEXIT_ERROR"]
    assert rows[0]["stage_trace"] == list(mod.STAGES)
    assert rows[1]["last_completed_stage"] == "sanitization_started"
    assert rows[2]["last_completed_stage"] == "canonical_hash_started"
    assert rows[3]["last_completed_stage"] == "json_dumps_started"
    assert rows[4]["last_completed_stage"] == "json_dumps_started"
    assert rows[5]["last_completed_stage"] == "stdout_write_started"
    assert rows[6]["last_completed_stage"] == "stdout_write_completed"
    assert rows[-1]["returncode"] == 0 and rows[-1]["stdout_marker_count"] == 0
    assert rows[-1]["stderr_exception_class"] == "RuntimeError"
    assert rows[-1]["stderr_exception_message"] == "synthetic_atexit_failure"
    assert all("Traceback" not in json.dumps(row) and ":\\" not in json.dumps(row) for row in rows)
    assert mod.canonical({k: v for k, v in result.items() if k != "canonical_result_sha256"}) == result["canonical_result_sha256"]


def test_classifier_edges_and_hash_determinism():
    p = mod.payload()
    p["canonical_result_sha256"] = mod.canonical(p)
    marker = (mod.PREFIX + json.dumps(p)).encode()
    assert mod.classify(0, marker, b"") == "TRANSPORT_OK"
    assert mod.classify(0, b"", b"") == "NO_MARKER_RC0_NO_STDERR"
    assert mod.classify(7, b"", b"") == "NO_MARKER_NONZERO_EXIT"
    assert mod.classify(0, marker + b"\n" + marker, b"") == "DUPLICATE_MARKER"
    assert mod.classify(0, mod.PREFIX.encode() + b"{", b"") == "MALFORMED_JSON"
    assert mod.classify(0, mod.PREFIX.encode() + b"{}", b"") == "CHILD_SCHEMA_INVALID"
    assert mod.classify(0, b"\xff", b"") == "STDOUT_DECODE_ERROR"
    assert mod.canonical(mod.payload()) == mod.canonical(mod.payload())


def test_static_binding_and_scope():
    binding = mod.static_binding(ROOT)
    assert binding["runner_sha256"] == mod.PR89_SHA
    assert binding["atexit_register"] and binding["parent_stderr_pipe"]
    assert binding["parent_stderr_durably_retained"] is False
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("import torch", "from torch", "laya.load(", "torch.load(",
                      "cuda.is_available(", "validation.jsonl", "train.jsonl", "held_out.jsonl"):
        assert forbidden not in source
