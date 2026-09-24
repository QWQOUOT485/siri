"""Write once, then verify the offline Stage B held-out evaluation snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import local_ai_stage_b_corpus as protocol
import local_ai_stage_b_final_selection as final


MERGED_MAIN_SHA = "347147324e8c83715dd7341d12c9dee023dffb16"
PRESEAL_MAIN_SHA = "7619baa4145b7525fad32a1bc62ec35afedd59aa"
SEAL_SCHEMA_VERSION = "stage-b-held-out-seal-v1"
SEAL_ALGORITHM_VERSION = "verified-byte-copy-write-once-v1"
DEFAULT_SOURCE_DIR = protocol.REPO_ROOT / "artifacts" / "local_ai" / "stage_b" / "final_v1"
DEFAULT_SEAL_DIR = protocol.REPO_ROOT / "artifacts" / "local_ai" / "stage_b" / "sealed_v1"
SEALED_ARTIFACT_PATH = "artifacts/local_ai/stage_b/sealed_v1/held_out.jsonl"
EXPECTED_SOURCE_FILES = frozenset({
    "train.jsonl", "validation.jsonl", "held_out.jsonl", "split_assignment.json",
    "selection_manifest.json", "corpus_manifest.json", "provenance_manifest.json", "README.md",
})
EXPECTED_SEAL_FILES = frozenset({"held_out.jsonl", "seal_manifest.json", "README.md"})
FROZEN_CANONICAL_CORPUS_SHA256 = "a7a7a673bbb5155bce7b163a3ef4a6bf8c3885b9a0c2b81a208d4a9304854e13"
FROZEN_CANONICAL_SPLIT_SHA256 = {
    "train": "c3793a6b8e4bb5068f5bd1d027c1b967be5fd18b88992db2b363270a4a832964",
    "validation": "9f3028c83e0c3f7e5402c239abe9f194a3e06309b43f3cd9344fb3475fdf21cd",
    "test": "6c9d960bd299c3c4cc07aa5f341b775d408d2b2f4191954512f588519d683594",
}
FROZEN_SPLIT_FILE_SHA256 = {
    "train.jsonl": "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2",
    "validation.jsonl": "297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a",
    "held_out.jsonl": "de392544b7a294cdf850ce2706509684b05c4ca346402c7ec60cf9031f979946",
}
FROZEN_MANIFEST_SELF_SHA256 = {
    "selection_manifest.json": ("selection_manifest_sha256", "973237c6b1437387f1bba21396fd4c60e0d0395112c07e1003e4764f676e143a"),
    "split_assignment.json": ("split_assignment_sha256", "84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37"),
    "corpus_manifest.json": ("manifest_sha256", "297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c"),
    "provenance_manifest.json": ("provenance_sha256", "d8158ead4034db387f9e4b7fa315b6ce60dcfe09f96caf909d4da5bcc7732e9d"),
}
EVALUATION_ONLY_CONSUMER_POLICY = {
    "status": "evaluation_only_no_current_compute_authorization",
    "forbidden_consumers": [
        "training", "fine_tuning", "checkpoint_selection", "validation_model_selection",
        "calibration", "threshold_fitting", "prompt_construction", "augmentation",
    ],
}
README = """# Stage B held-out seal v1

`held_out.jsonl` is a byte-identical, write-once snapshot of the frozen
`final_v1/held_out.jsonl`. Its labels are evaluation-only. They are unavailable
to training, fine-tuning, checkpoint or model selection, calibration, threshold
fitting, prompts, and augmentation. This seal grants no evaluation/model compute
authorization; that requires a separate reviewed gate.

The repository-owned seal command creates this directory only when absent.
Thereafter use `--verify` to check source and sealed identities without writes.
Any mismatch or unexpected file fails closed. Git and filesystem read-only bits
alone are not the integrity boundary. The historical `final_v1` manifests keep
their original `held_out_sealed=false` state; only `seal_manifest.json` records
completion of this seal step.
"""


class HeldOutSealError(ValueError):
    """A source or sealed identity violates the frozen write-once boundary."""


@dataclass(frozen=True)
class SourceEvidence:
    held_out_bytes: bytes
    seal_manifest: Mapping[str, Any]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256(protocol.canonical_json(value).encode("utf-8"))


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _local_path(path: Path | str, *, field: str) -> Path:
    safe = protocol.validate_local_path(path, field=field)
    # Reject symlinked or junction/reparse components, including parent dirs.
    for component in (safe, *safe.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise HeldOutSealError(f"{field} traverses a redirected path")
        if component.exists() and getattr(component.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
            raise HeldOutSealError(f"{field} traverses a reparse point")
    return safe


def _normal_file(path: Path, *, field: str) -> bytes:
    _local_path(path, field=field)
    if not path.is_file():
        raise HeldOutSealError(f"{field} is not a normal local file")
    return path.read_bytes()


def _read_object(data: bytes, *, field: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HeldOutSealError(f"{field} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise HeldOutSealError(f"{field} is not a JSON object")
    return value


def _verify_self_hash(value: Mapping[str, Any], field: str, expected: str) -> None:
    unsigned = dict(value)
    if unsigned.pop(field, None) != expected or _canonical_hash(unsigned) != expected:
        raise HeldOutSealError(f"{field} does not match the frozen self-hash")


def _read_split(data: bytes, *, name: str) -> tuple[protocol.StageBRecord, ...]:
    try:
        lines = data.decode("utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
        return tuple(protocol.StageBRecord.from_mapping(row) for row in rows)
    except (UnicodeError, json.JSONDecodeError, protocol.StageBCorpusError) as exc:
        raise HeldOutSealError(f"{name} is not valid closed-schema JSONL") from exc


def _verify_group_assignment(
    splits: Mapping[str, tuple[protocol.StageBRecord, ...]], assignment: Mapping[str, Any],
    v6_groups: Mapping[str, final.SourceGroup],
) -> None:
    entries = assignment.get("groups")
    if not isinstance(entries, dict) or set(entries) != set(v6_groups):
        raise HeldOutSealError("split assignment does not cover frozen v6 groups")
    split_by_group: dict[str, str] = {}
    for split, records in splits.items():
        group_counts = Counter(record.source_group_id for record in records)
        expected_groups = {"train": 300, "validation": 100, "test": 100}[split]
        if len(group_counts) != expected_groups or set(group_counts.values()) != {6}:
            raise HeldOutSealError("final split is not made of complete six-row groups")
        for record in records:
            if record.source_group_id in split_by_group and split_by_group[record.source_group_id] != split:
                raise HeldOutSealError("source group crosses final splits")
            split_by_group[record.source_group_id] = split
            source_row = next((row for row in v6_groups[record.source_group_id].rows if row["candidate_id"] == record.case_id), None)
            if source_row is None or record.to_dict() != final._record(source_row).to_dict():
                raise HeldOutSealError("final row differs from frozen reviewed v6 candidate")
    if len(split_by_group) != 500:
        raise HeldOutSealError("selected source group count is not 500")
    for group_id, group in v6_groups.items():
        entry = entries[group_id]
        candidate_ids = [row["candidate_id"] for row in group.rows]
        expected_state = split_by_group.get(group_id, "excluded")
        if (
            not isinstance(entry, dict)
            or entry.get("state") != expected_state
            or entry.get("class") != group.class_key
            or entry.get("candidate_ids") != candidate_ids
            or entry.get("membership_sha256") != _canonical_hash(candidate_ids)
        ):
            raise HeldOutSealError("split assignment differs from frozen source groups")


def load_source_evidence(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    *,
    stage_a_path: Path = protocol.DEFAULT_STAGE_A_CORPUS_PATH,
    v6_artifacts_dir: Path = final.review.DEFAULT_STAGE_B_ARTIFACT_DIR,
) -> SourceEvidence:
    """Read-only verification of the exact reviewed pre-seal source."""

    source_dir = _local_path(source_dir, field="source_dir")
    stage_a_path = _local_path(stage_a_path, field="stage_a_path")
    v6_artifacts_dir = _local_path(v6_artifacts_dir, field="v6_artifacts_dir")
    if not source_dir.is_dir() or {entry.name for entry in source_dir.iterdir()} != EXPECTED_SOURCE_FILES:
        raise HeldOutSealError("final_v1 artifact set is incomplete or unexpected")
    files = {name: _normal_file(source_dir / name, field=name) for name in sorted(EXPECTED_SOURCE_FILES)}
    for name, expected in FROZEN_SPLIT_FILE_SHA256.items():
        if _sha256(files[name]) != expected:
            raise HeldOutSealError(f"frozen {name} byte SHA-256 mismatch")
    manifests = {
        name: _read_object(files[name], field=name) for name in FROZEN_MANIFEST_SELF_SHA256
    }
    for name, (field, expected) in FROZEN_MANIFEST_SELF_SHA256.items():
        _verify_self_hash(manifests[name], field, expected)
    selection = manifests["selection_manifest.json"]
    assignment = manifests["split_assignment.json"]
    corpus = manifests["corpus_manifest.json"]
    provenance = manifests["provenance_manifest.json"]
    if selection.get("artifact_file_sha256") != {
        name: _sha256(files[name]) for name in sorted(EXPECTED_SOURCE_FILES - {"selection_manifest.json"})
    }:
        raise HeldOutSealError("final_v1 artifact byte manifest mismatch")
    if (
        selection.get("starting_main_sha") != PRESEAL_MAIN_SHA
        or assignment.get("starting_main_sha") != PRESEAL_MAIN_SHA
        or selection.get("canonical_corpus_sha256") != FROZEN_CANONICAL_CORPUS_SHA256
        or selection.get("canonical_split_sha256") != FROZEN_CANONICAL_SPLIT_SHA256
        or corpus.get("corpus_sha256") != FROZEN_CANONICAL_CORPUS_SHA256
        or corpus.get("split_sha256") != FROZEN_CANONICAL_SPLIT_SHA256
        or provenance.get("canonical_corpus_sha256") != FROZEN_CANONICAL_CORPUS_SHA256
        or provenance.get("final_split_sha256") != FROZEN_CANONICAL_SPLIT_SHA256
        or selection.get("decision_manifest_sha256") != final.DECISION_MANIFEST_SHA256
        or selection.get("review_progress_sha256") != final.REVIEW_PROGRESS_SHA256
        or selection.get("source_identities") != dict(final.review.REVIEWED_SOURCE_IDENTITIES)
        or assignment.get("source_identities") != dict(final.review.REVIEWED_SOURCE_IDENTITIES)
        or selection.get("stage_a_sha256") != protocol.EXPECTED_STAGE_A_SHA256
        or selection.get("near_duplicate_config_sha256") != protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256
        or corpus.get("near_duplicate_policy", {}).get("config_sha256") != protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256
    ):
        raise HeldOutSealError("final_v1 frozen source identity mismatch")
    for value in (selection, assignment):
        if value.get("final_split_assigned") is not True or value.get("held_out_sealed") is not False:
            raise HeldOutSealError("source is not the frozen pre-seal split")
    if any(selection.get(flag) is not False for flag in (
        "training_authorized", "model_compute_authorized", "semantic_memory_enabled", "local_ai_fallback_approved"
    )):
        raise HeldOutSealError("pre-seal source carries unauthorized authority")
    if assignment.get("group_state_counts") != {"train": 300, "validation": 100, "test": 100, "excluded": 100}:
        raise HeldOutSealError("pre-seal source group counts mismatch")
    if protocol.DEFAULT_NEAR_DUPLICATE_CONFIG.config_sha256 != protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256:
        raise HeldOutSealError("active near-duplicate policy differs from frozen identity")
    if protocol.stage_a_identity(stage_a_path) != {
        "case_count": 109, "sha256": protocol.EXPECTED_STAGE_A_SHA256
    }:
        raise HeldOutSealError("Stage A frozen identity differs")

    verified_v6 = final.load_verified_inputs(v6_artifacts_dir)
    v6_groups = final._groups(verified_v6.source)
    if (
        selection.get("source_identities") != dict(verified_v6.source.identities)
        or assignment.get("decision_manifest_sha256") != verified_v6.decision_manifest["decision_manifest_sha256"]
        or assignment.get("review_progress_sha256") != verified_v6.review_progress["review_progress_sha256"]
    ):
        raise HeldOutSealError("upstream v6 review identity differs")
    splits = {name: _read_split(files[filename], name=filename) for name, filename in (
        ("train", "train.jsonl"), ("validation", "validation.jsonl"), ("test", "held_out.jsonl")
    )}
    _verify_group_assignment(splits, assignment, v6_groups)
    if {name: len(records) for name, records in splits.items()} != {"train": 1800, "validation": 600, "test": 600}:
        raise HeldOutSealError("frozen final split row counts differ")
    validated = protocol.validate_protocol_corpus(
        splits, stage_a_path=stage_a_path, verify_stage_a_identity=True
    )
    if validated.manifest_dict() != corpus:
        raise HeldOutSealError("authoritative protocol manifest differs from frozen final_v1")
    if len({record.source_group_id for record in splits["test"]}) != 100:
        raise HeldOutSealError("held-out does not have 100 whole source groups")

    manifest: dict[str, Any] = {
        "seal_schema_version": SEAL_SCHEMA_VERSION,
        "seal_algorithm_version": SEAL_ALGORITHM_VERSION,
        "starting_main_sha": MERGED_MAIN_SHA,
        "source_canonical_corpus_sha256": FROZEN_CANONICAL_CORPUS_SHA256,
        "source_canonical_split_sha256": dict(FROZEN_CANONICAL_SPLIT_SHA256),
        "selection_manifest_sha256": FROZEN_MANIFEST_SELF_SHA256["selection_manifest.json"][1],
        "split_assignment_sha256": FROZEN_MANIFEST_SELF_SHA256["split_assignment.json"][1],
        "corpus_manifest_sha256": FROZEN_MANIFEST_SELF_SHA256["corpus_manifest.json"][1],
        "provenance_manifest_sha256": FROZEN_MANIFEST_SELF_SHA256["provenance_manifest.json"][1],
        "source_held_out_byte_sha256": FROZEN_SPLIT_FILE_SHA256["held_out.jsonl"],
        "sealed_held_out_byte_sha256": FROZEN_SPLIT_FILE_SHA256["held_out.jsonl"],
        "sealed_held_out_canonical_sha256": FROZEN_CANONICAL_SPLIT_SHA256["test"],
        "sealed_row_count": len(splits["test"]),
        "sealed_group_count": len({record.source_group_id for record in splits["test"]}),
        "stage_a_sha256": protocol.EXPECTED_STAGE_A_SHA256,
        "near_duplicate_config_sha256": protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256,
        "v6_candidate_corpus_sha256": verified_v6.source.identities["candidate_corpus_sha256"],
        "v6_candidate_manifest_sha256": verified_v6.source.identities["candidate_manifest_sha256"],
        "decision_manifest_sha256": verified_v6.decision_manifest["decision_manifest_sha256"],
        "review_progress_sha256": verified_v6.review_progress["review_progress_sha256"],
        "sealed_artifact_path": SEALED_ARTIFACT_PATH,
        "consumer_policy": EVALUATION_ONLY_CONSUMER_POLICY,
        "final_split_assigned": True,
        "held_out_sealed": True,
        "training_authorized": False,
        "model_compute_authorized": False,
        "semantic_memory_enabled": False,
        "local_ai_fallback_approved": False,
    }
    manifest["seal_manifest_sha256"] = _canonical_hash(manifest)
    return SourceEvidence(files["held_out.jsonl"], manifest)


def create_seal(source_dir: Path = DEFAULT_SOURCE_DIR, seal_dir: Path = DEFAULT_SEAL_DIR) -> Mapping[str, Any]:
    """Create a seal only once; an existing directory is never overwritten."""

    target = _local_path(seal_dir, field="seal_dir")
    if target.exists() or target.is_symlink():
        raise HeldOutSealError("seal directory already exists; use verify-only mode")
    evidence = load_source_evidence(source_dir)
    target.mkdir(parents=False, exist_ok=False)
    for name, data in (
        ("held_out.jsonl", evidence.held_out_bytes),
        ("seal_manifest.json", _json_bytes(evidence.seal_manifest)),
        ("README.md", README.encode("utf-8")),
    ):
        with (target / name).open("xb") as stream:
            stream.write(data)
    verify_seal(source_dir, target)
    return evidence.seal_manifest


def verify_seal(source_dir: Path = DEFAULT_SOURCE_DIR, seal_dir: Path = DEFAULT_SEAL_DIR) -> Mapping[str, Any]:
    """Read-only verification of source, sealed bytes, and the seal manifest."""

    evidence = load_source_evidence(source_dir)
    target = _local_path(seal_dir, field="seal_dir")
    if not target.is_dir() or {entry.name for entry in target.iterdir()} != EXPECTED_SEAL_FILES:
        raise HeldOutSealError("sealed directory is missing or has unexpected files")
    sealed = _normal_file(target / "held_out.jsonl", field="sealed held_out.jsonl")
    raw_manifest = _normal_file(target / "seal_manifest.json", field="seal_manifest.json")
    readme = _normal_file(target / "README.md", field="sealed README.md")
    if sealed != evidence.held_out_bytes or _sha256(sealed) != FROZEN_SPLIT_FILE_SHA256["held_out.jsonl"]:
        raise HeldOutSealError("sealed held-out bytes differ from frozen source")
    if _canonical_hash(protocol._canonical_records(_read_split(sealed, name="sealed held_out.jsonl"))) != FROZEN_CANONICAL_SPLIT_SHA256["test"]:
        raise HeldOutSealError("sealed held-out canonical split differs from frozen identity")
    if readme != README.encode("utf-8"):
        raise HeldOutSealError("sealed README differs from frozen seal instructions")
    manifest = _read_object(raw_manifest, field="seal_manifest.json")
    _verify_self_hash(manifest, "seal_manifest_sha256", evidence.seal_manifest["seal_manifest_sha256"])
    if manifest != evidence.seal_manifest:
        raise HeldOutSealError("seal manifest differs from deterministic frozen evidence")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--seal-dir", type=Path, default=DEFAULT_SEAL_DIR)
    parser.add_argument("--verify", action="store_true", help="verify an existing seal without writes")
    args = parser.parse_args()
    result = (
        verify_seal(args.source_dir, args.seal_dir)
        if args.verify or args.seal_dir.exists()
        else create_seal(args.source_dir, args.seal_dir)
    )
    print(json.dumps({
        "seal_manifest_sha256": result["seal_manifest_sha256"],
        "sealed_row_count": result["sealed_row_count"],
        "sealed_group_count": result["sealed_group_count"],
        "held_out_sealed": result["held_out_sealed"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
