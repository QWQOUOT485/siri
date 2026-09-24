"""Offline integrity checks for the write-once Stage B held-out seal."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import local_ai_stage_b_held_out_seal as seal  # noqa: E402


@pytest.fixture(scope="module")
def evidence() -> seal.SourceEvidence:
    return seal.load_source_evidence()


def _source_copy(tmp_path: Path) -> Path:
    source = tmp_path / "final_v1"
    shutil.copytree(seal.DEFAULT_SOURCE_DIR, source)
    return source


def _fast_source(monkeypatch: pytest.MonkeyPatch, evidence: seal.SourceEvidence) -> None:
    monkeypatch.setattr(seal, "load_source_evidence", lambda source_dir=seal.DEFAULT_SOURCE_DIR: evidence)


def test_exact_source_identities_and_shape(evidence: seal.SourceEvidence) -> None:
    assert evidence.seal_manifest["source_canonical_corpus_sha256"] == seal.FROZEN_CANONICAL_CORPUS_SHA256
    assert evidence.seal_manifest["source_canonical_split_sha256"] == seal.FROZEN_CANONICAL_SPLIT_SHA256
    assert evidence.seal_manifest["sealed_row_count"] == 600
    assert evidence.seal_manifest["sealed_group_count"] == 100
    assert hashlib.sha256(evidence.held_out_bytes).hexdigest() == seal.FROZEN_SPLIT_FILE_SHA256["held_out.jsonl"]
    assert evidence.seal_manifest["stage_a_sha256"] == seal.protocol.EXPECTED_STAGE_A_SHA256
    assert evidence.seal_manifest["near_duplicate_config_sha256"] == seal.protocol.FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256


def test_frozen_seal_verifies_without_mutation() -> None:
    paths = [seal.DEFAULT_SOURCE_DIR / name for name in seal.EXPECTED_SOURCE_FILES]
    paths += [seal.DEFAULT_SEAL_DIR / name for name in seal.EXPECTED_SEAL_FILES]
    before = {path: path.read_bytes() for path in paths}
    first = seal.verify_seal()
    second = seal.verify_seal()
    assert first == second
    assert {path: path.read_bytes() for path in paths} == before
    assert first["sealed_held_out_canonical_sha256"] == seal.FROZEN_CANONICAL_SPLIT_SHA256["test"]
    assert first["seal_manifest_sha256"] == seal._canonical_hash({key: value for key, value in first.items() if key != "seal_manifest_sha256"})
    assert first["final_split_assigned"] is first["held_out_sealed"] is True
    assert all(first[flag] is False for flag in (
        "training_authorized", "model_compute_authorized", "semantic_memory_enabled", "local_ai_fallback_approved"
    ))
    for name in ("selection_manifest.json", "split_assignment.json"):
        assert json.loads(before[seal.DEFAULT_SOURCE_DIR / name])["held_out_sealed"] is False


def test_source_byte_mutation_fails_closed(tmp_path: Path) -> None:
    source = _source_copy(tmp_path)
    with (source / "held_out.jsonl").open("ab") as stream:
        stream.write(b"\n")
    with pytest.raises(seal.HeldOutSealError, match="byte SHA-256"):
        seal.load_source_evidence(source)


def test_source_manifest_self_hash_mutation_fails_closed(tmp_path: Path) -> None:
    source = _source_copy(tmp_path)
    path = source / "selection_manifest.json"
    value = json.loads(path.read_bytes())
    value["held_out_sealed"] = True
    path.write_bytes(seal._json_bytes(value))
    with pytest.raises(seal.HeldOutSealError, match="self-hash"):
        seal.load_source_evidence(source)


@pytest.mark.parametrize("field", ["canonical_corpus_sha256", "canonical_split_sha256"])
def test_source_corpus_identity_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    source = _source_copy(tmp_path)
    path = source / "selection_manifest.json"
    value = json.loads(path.read_bytes())
    value[field] = "0" * 64
    value["selection_manifest_sha256"] = seal._canonical_hash({k: v for k, v in value.items() if k != "selection_manifest_sha256"})
    path.write_bytes(seal._json_bytes(value))
    changed = dict(seal.FROZEN_MANIFEST_SELF_SHA256)
    changed["selection_manifest.json"] = ("selection_manifest_sha256", value["selection_manifest_sha256"])
    monkeypatch.setattr(seal, "FROZEN_MANIFEST_SELF_SHA256", changed)
    with pytest.raises(seal.HeldOutSealError, match="source identity mismatch"):
        seal.load_source_evidence(source)


def test_stage_a_mutation_fails_closed(tmp_path: Path) -> None:
    stage_a = tmp_path / "stage_a.json"
    rows = json.loads(seal.protocol.DEFAULT_STAGE_A_CORPUS_PATH.read_bytes())
    rows[0]["input"] += "變更"
    stage_a.write_bytes(seal._json_bytes(rows))
    with pytest.raises((seal.HeldOutSealError, seal.protocol.StageBCorpusError), match="Stage A"):
        seal.load_source_evidence(stage_a_path=stage_a)


def test_near_duplicate_config_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seal.protocol, "FROZEN_STAGE_B_NEAR_DUPLICATE_CONFIG_SHA256", "0" * 64)
    with pytest.raises(seal.HeldOutSealError, match="source identity mismatch|near-duplicate"):
        seal.load_source_evidence()


def test_write_once_and_clean_independent_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence: seal.SourceEvidence) -> None:
    _fast_source(monkeypatch, evidence)
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    seal.create_seal(seal.DEFAULT_SOURCE_DIR, first_dir)
    seal.create_seal(seal.DEFAULT_SOURCE_DIR, second_dir)
    first = {name: (first_dir / name).read_bytes() for name in seal.EXPECTED_SEAL_FILES}
    assert first == {name: (second_dir / name).read_bytes() for name in seal.EXPECTED_SEAL_FILES}
    assert first["held_out.jsonl"] == evidence.held_out_bytes
    assert hashlib.sha256(first["held_out.jsonl"]).hexdigest() == seal.FROZEN_SPLIT_FILE_SHA256["held_out.jsonl"]
    assert seal._canonical_hash(seal.protocol._canonical_records(seal._read_split(first["held_out.jsonl"], name="held_out"))) == seal.FROZEN_CANONICAL_SPLIT_SHA256["test"]
    with pytest.raises(seal.HeldOutSealError, match="already exists"):
        seal.create_seal(seal.DEFAULT_SOURCE_DIR, first_dir)
    assert first == {name: (first_dir / name).read_bytes() for name in seal.EXPECTED_SEAL_FILES}


@pytest.mark.parametrize("mutation", ["held_out", "manifest", "readme", "extra"])
def test_existing_seal_tampering_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence: seal.SourceEvidence, mutation: str
) -> None:
    _fast_source(monkeypatch, evidence)
    target = tmp_path / "sealed_v1"
    seal.create_seal(seal.DEFAULT_SOURCE_DIR, target)
    if mutation == "held_out":
        (target / "held_out.jsonl").write_bytes(b"wrong")
    elif mutation == "manifest":
        manifest = json.loads((target / "seal_manifest.json").read_bytes())
        manifest["training_authorized"] = True
        (target / "seal_manifest.json").write_bytes(seal._json_bytes(manifest))
    elif mutation == "readme":
        (target / "README.md").write_text("wrong", encoding="utf-8")
    else:
        (target / "unexpected.txt").write_text("wrong", encoding="utf-8")
    with pytest.raises(seal.HeldOutSealError):
        seal.verify_seal(seal.DEFAULT_SOURCE_DIR, target)


def test_local_paths_and_symlinks_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence: seal.SourceEvidence) -> None:
    real_loader = seal.load_source_evidence
    real_is_symlink = Path.is_symlink
    _fast_source(monkeypatch, evidence)
    for bad in (r"\\server\share\sealed_v1", r"\\?\C:\temp\sealed_v1"):
        with pytest.raises((seal.HeldOutSealError, seal.protocol.StageBCorpusError, ValueError)):
            seal.create_seal(seal.DEFAULT_SOURCE_DIR, Path(bad))
    target = tmp_path / "real"
    seal.create_seal(seal.DEFAULT_SOURCE_DIR, target)
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(target, target_is_directory=True)
    except OSError:
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == redirected or real_is_symlink(path))
    with pytest.raises(seal.HeldOutSealError, match="redirected"):
        seal.verify_seal(seal.DEFAULT_SOURCE_DIR, redirected)
    source = _source_copy(tmp_path)
    source_file = source / "held_out.jsonl"
    source_file.unlink()
    try:
        source_file.symlink_to(seal.DEFAULT_SOURCE_DIR / "held_out.jsonl")
    except OSError:
        source_file.write_bytes(seal.DEFAULT_SOURCE_DIR.joinpath("held_out.jsonl").read_bytes())
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == source_file or real_is_symlink(path))
    monkeypatch.setattr(seal, "load_source_evidence", real_loader)
    with pytest.raises(seal.HeldOutSealError, match="redirected"):
        seal.load_source_evidence(source)


def test_selection_path_has_no_runtime_or_model_dependency() -> None:
    source = (ROOT / "scripts" / "local_ai_stage_b_held_out_seal.py").read_text(encoding="utf-8")
    imports = [node for node in ast.walk(ast.parse(source)) if isinstance(node, (ast.Import, ast.ImportFrom))]
    roots = {
        alias.name.split(".")[0]
        for node in imports
        for alias in node.names
        if isinstance(node, ast.Import)
    }
    roots.update(node.module.split(".")[0] for node in imports if isinstance(node, ast.ImportFrom) and node.module)
    assert roots <= {
        "__future__", "argparse", "hashlib", "json", "collections", "dataclasses", "pathlib", "typing",
        "local_ai_stage_b_corpus", "local_ai_stage_b_final_selection",
    }
