"""Read-only train-subset preflight. This blocked gate contains no model compute."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from typing import Any

import local_ai_stage_b_corpus as corpus
import local_ai_stage_b_held_out_seal as seal

BASE = "57a07b11f8ae322d39be9379f7423b924880aa0b"
TRAIN = corpus.REPO_ROOT / "artifacts/local_ai/stage_b/final_v1/train.jsonl"
TRAIN_SHA = "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2"
SEAL_SHA = "5606a4803788577d29bda39e9d40319a43098d857c795d7c8a882f2f842b6eef"
DATA = "STOP_LAYA_TRAINING_PIPELINE_DATA_BOUNDARY"
AUTHORITY_FLAGS = dict.fromkeys(("training_authorized", "model_compute_authorized",
    "semantic_memory_enabled", "local_ai_fallback_approved",
    "LOCAL_SEMANTIC_MEMORY_ENABLED", "LOCAL_AI_FALLBACK_APPROVED"), False)
STRATA = tuple(f"play_artist_{artist}_album_{album}"
               for artist, album in (("present", "present"), ("present", "absent"),
                                     ("absent", "present"), ("absent", "absent"))) + tuple(
    "unknown_" + reason for reason in
    ("missing_track", "artist_only", "unresolved_reference", "ambiguous_version")) + (
    "deterministic_only", "safety_only")


class DataBoundaryError(ValueError):
    """The frozen source cannot satisfy this task's declared subset."""


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise DataBoundaryError(reason)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_train(data: bytes) -> list[corpus.StageBRecord]:
    require(hashlib.sha256(data).hexdigest() == TRAIN_SHA, "train_byte_sha_mismatch")
    try:
        lines = data.decode("utf-8", "strict").splitlines()
        require(len(lines) == 1800, "train_row_count_mismatch")
        rows = [corpus.StageBRecord.from_mapping(json.loads(line)) for line in lines]
    except DataBoundaryError:
        raise
    except (ValueError, TypeError) as exc:
        raise DataBoundaryError("train_schema_invalid") from exc
    require(len({row.case_id for row in rows}) == 1800, "train_case_ids_not_unique")
    return rows


def verified_data() -> tuple[list[corpus.StageBRecord], dict[str, Any]]:
    # Only TRAIN supplies selectable rows. The existing verifier's broader reads
    # establish integrity only and return no validation/held-out/Stage A rows here.
    rows = parse_train(seal._normal_file(TRAIN, field="train_input"))
    try:
        manifest = seal.verify_seal()
    except (seal.HeldOutSealError, corpus.StageBCorpusError) as exc:
        raise DataBoundaryError("corpus_or_seal_verification_failed") from exc
    require(manifest["seal_manifest_sha256"] == SEAL_SHA
            and manifest["sealed_row_count"] == 600 and manifest["sealed_group_count"] == 100
            and manifest["final_split_assigned"] is True and manifest["held_out_sealed"] is True,
            "seal_identity_mismatch")
    require(all(manifest[key] is False for key in AUTHORITY_FLAGS if key.islower()),
            "persistent_authority_flag_changed")
    require(all(value is False for value in AUTHORITY_FLAGS.values())
            and all(os.environ.get(key, "false").casefold() == "false" for key in AUTHORITY_FLAGS),
            "authority_flag_changed")
    return rows, {"train_sha256": TRAIN_SHA, "train_rows": len(rows),
        "seal_manifest_sha256": manifest["seal_manifest_sha256"],
        "canonical_corpus_sha256": manifest["source_canonical_corpus_sha256"],
        "canonical_split_sha256": manifest["source_canonical_split_sha256"],
        **{key: manifest[key] for key in ("selection_manifest_sha256", "split_assignment_sha256",
                                        "corpus_manifest_sha256", "provenance_manifest_sha256")},
        "split_file_sha256": dict(seal.FROZEN_SPLIT_FILE_SHA256),
        "authoritative_schema_groups_leakage_near_duplicates": "passed"}


def stratum(row: corpus.StageBRecord) -> str | None:
    if row.ai_scope in ("deterministic_only", "safety_only"):
        return row.ai_scope
    if row.ai_scope == "supported" and row.expected.intent == "spotify_play_track":
        return f"play_artist_{row.optional_slot_status['artist']}_album_{row.optional_slot_status['album']}"
    if row.ai_scope == "supported" and row.expected.intent == "unknown":
        return "unknown_" + str(row.negative_reason)
    return None


def select_subset(rows: list[corpus.StageBRecord]) -> tuple[list[corpus.StageBRecord], dict[str, Any]]:
    counts: Counter[str] = Counter()
    selected = []
    for row in rows:
        key = stratum(row)
        if key in STRATA and counts[key] < 4:
            selected.append(row)
            counts[key] += 1
    if dict(counts) != dict.fromkeys(STRATA, 4) or len({row.case_id for row in selected}) != 40:
        raise DataBoundaryError("fixed_strata_incomplete_or_duplicate")
    eligible = [row.case_id for row in selected if row.ai_scope == "supported"]
    blocked = [row.case_id for row in selected if row.ai_scope != "supported"]
    require(len(eligible) == 32 and len(blocked) == 8, "subset_gate_count_mismatch")
    manifest = {"train_file_sha256": TRAIN_SHA, "selection_algorithm": "canonical-file-first-four-per-stratum-v1",
                "case_ids": [row.case_id for row in selected],
                "source_group_ids": [row.source_group_id for row in selected],
                "per_stratum_counts": dict(counts), "model_eligible_case_ids": eligible,
                "blocked_case_ids": blocked, "source_subset_rows": 40,
                "model_eligible_rows": 32, "blocked_before_model": 8,
                "batches": [eligible[i:i + 8] for i in range(0, 32, 8)]}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    return selected, manifest


def preflight() -> dict[str, Any]:
    result: dict[str, Any] = {"schema": "laya-training-pipeline-data-preflight-v1",
        "repo_base": BASE, "status": DATA, "authority_flags": dict(AUTHORITY_FLAGS),
        "live_invocations": 0, "model_loads": 0, "optimizer_steps": 0,
        "checkpoint_created": False}
    before = None
    try:
        rows, before = verified_data()
        result["data_identity_before"] = before
        available = Counter(stratum(row) for row in rows)
        result["available_per_stratum"] = {key: available[key] for key in STRATA}
        result["required_per_stratum"] = dict.fromkeys(STRATA, 4)
        result["deficient_strata"] = {key: available[key] for key in STRATA if available[key] < 4}
        _, manifest = select_subset(rows)
        result["subset_manifest"] = manifest
        result["status"] = "DATA_PREFLIGHT_PASSED_NO_MODEL_COMPUTE"
    except DataBoundaryError as exc:
        result["blocker"] = str(exc)
    finally:
        if before is not None:
            try:
                _, after = verified_data()
                result["data_identity_after"] = after
                require(before == after, "frozen_data_mutated")
            except DataBoundaryError as exc:
                result.update(status=DATA, blocker=str(exc))
    result["canonical_report_sha256"] = canonical_hash(result)
    return result


def main() -> int:
    require(not sys.argv[1:], "unexpected_arguments")
    result = preflight()
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result["status"] == "DATA_PREFLIGHT_PASSED_NO_MODEL_COMPUTE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
