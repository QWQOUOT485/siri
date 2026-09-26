"""Read-only data blocker and synthetic selector tests; no model or GPU."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_laya_training_pipeline_smoke as smoke


@pytest.fixture
def synthetic_rows():
    rows = []
    for key in smoke.STRATA:
        for variant in range(6):
            play = key.startswith("play_")
            supported = play or key.startswith("unknown_")
            artist = play and "artist_present" in key
            album = play and "album_present" in key
            row = {"case_id": f"unit-{len(rows):03}", "source_group_id": f"unit-group-{key}",
                "utterance": "Tune Artist Album", "language_tag": "en", "language_slice": "english",
                "ai_scope": "supported" if supported else key,
                "expected": {"intent": "spotify_play_track" if play else "unknown",
                    "track": {"text": "Tune", "start": 0, "end": 4} if play else None,
                    "artist": {"text": "Artist", "start": 5, "end": 11} if artist else None,
                    "album": {"text": "Album", "start": 12, "end": 17} if album else None},
                "optional_slot_status": {"artist": "present" if artist else "absent",
                                         "album": "present" if album else "absent"} if play else None,
                "negative_reason": None if play else key.removeprefix("unknown_") if supported else
                    "playback_control" if key == "deterministic_only" else "hostile_system",
                "template_family": "unit", "generator_version": "synthetic-unit-only"}
            rows.append(smoke.corpus.StageBRecord.from_mapping(row))
    return rows


def test_exact_train_byte_identity_and_count(monkeypatch):
    data = smoke.TRAIN.read_bytes()
    assert hashlib.sha256(data).hexdigest() == smoke.TRAIN_SHA
    assert len(smoke.parse_train(data)) == 1800
    with pytest.raises(smoke.DataBoundaryError, match="train_byte_sha_mismatch"):
        smoke.parse_train(data + b"\n")
    shortened = b"\n".join(data.splitlines()[:-1])
    monkeypatch.setattr(smoke, "TRAIN_SHA", hashlib.sha256(shortened).hexdigest())
    with pytest.raises(smoke.DataBoundaryError, match="train_row_count_mismatch"):
        smoke.parse_train(shortened)


def test_actual_train_has_two_missing_strata_and_no_manifest():
    rows = smoke.parse_train(smoke.TRAIN.read_bytes())
    available = {key: sum(smoke.stratum(row) == key for row in rows) for key in smoke.STRATA}
    assert list(available.values()) == [408, 204, 174, 114, 300, 300, 0, 0, 180, 120]
    with pytest.raises(smoke.DataBoundaryError, match="fixed_strata_incomplete_or_duplicate"):
        smoke.select_subset(rows)


def test_synthetic_selector_first_four_per_stratum_and_canonical_order(synthetic_rows):
    chosen, manifest = smoke.select_subset(synthetic_rows)
    assert smoke.select_subset(synthetic_rows) == (chosen, manifest)
    assert len(chosen) == len(manifest["case_ids"]) == len(manifest["source_group_ids"]) == 40
    assert manifest["per_stratum_counts"] == dict.fromkeys(smoke.STRATA, 4)
    for key in smoke.STRATA:
        assert [row.case_id for row in chosen if smoke.stratum(row) == key] == [
            row.case_id for row in synthetic_rows if smoke.stratum(row) == key][:4]
    assert [row.case_id for row in synthetic_rows if row.case_id in manifest["case_ids"]] == manifest["case_ids"]
    assert sum(row.expected.intent == "spotify_play_track" for row in chosen) == 16
    assert sum(row.ai_scope == "supported" and row.expected.intent == "unknown" for row in chosen) == 16
    assert sum(row.ai_scope == "deterministic_only" for row in chosen) == 4
    assert sum(row.ai_scope == "safety_only" for row in chosen) == 4
    unsigned = dict(manifest)
    assert unsigned.pop("manifest_sha256") == smoke.canonical_hash(unsigned)
    assert "utterance" not in smoke.canonical_bytes(manifest).decode()
    assert "Tune" not in smoke.canonical_bytes(manifest).decode()


def test_synthetic_eligibility_partition_and_four_fixed_batches(synthetic_rows):
    chosen, manifest = smoke.select_subset(synthetic_rows)
    assert manifest["source_subset_rows"] == 40
    assert manifest["model_eligible_rows"] == 32
    assert manifest["blocked_before_model"] == 8
    assert [len(batch) for batch in manifest["batches"]] == [8] * 4
    assert sum(manifest["batches"], []) == manifest["model_eligible_case_ids"]
    assert len(set(sum(manifest["batches"], []))) == 32
    assert not set(manifest["model_eligible_case_ids"]) & set(manifest["blocked_case_ids"])
    assert [row.case_id for row in chosen if row.ai_scope == "supported"] == manifest["model_eligible_case_ids"]
    assert [row.case_id for row in chosen if row.ai_scope != "supported"] == manifest["blocked_case_ids"]


def test_missing_or_duplicate_strata_fail_closed(synthetic_rows):
    with pytest.raises(smoke.DataBoundaryError, match="fixed_strata"):
        smoke.select_subset(synthetic_rows[:8])
    broken = list(synthetic_rows)
    broken[1] = broken[0]
    with pytest.raises(smoke.DataBoundaryError, match="fixed_strata"):
        smoke.select_subset(broken)


def test_closed_train_schema_is_checked(monkeypatch):
    rows = [json.loads(line) for line in smoke.TRAIN.read_bytes().splitlines()]
    rows[0]["extra"] = "forbidden"
    data = b"\n".join(smoke.canonical_bytes(row) for row in rows)
    monkeypatch.setattr(smoke, "TRAIN_SHA", hashlib.sha256(data).hexdigest())
    with pytest.raises(smoke.DataBoundaryError, match="train_schema_invalid"):
        smoke.parse_train(data)


def test_only_train_supplies_selector_rows_and_no_compute_imports():
    source = Path(smoke.__file__).read_text(encoding="utf-8")
    assert smoke.TRAIN.relative_to(smoke.corpus.REPO_ROOT).as_posix() == "artifacts/local_ai/stage_b/final_v1/train.jsonl"
    for forbidden in ("validation.jsonl", "held_out.jsonl", "ai_intent_cases.json", "load_fixture(",
                      "import torch", "import laya", "subprocess", "transformers"):
        assert forbidden not in source
    assert "rows = parse_train(seal._normal_file(TRAIN" in source
    assert "manifest = seal.verify_seal()" in source


def test_blocked_preflight_has_no_subset_or_live_result(monkeypatch):
    rows = smoke.parse_train(smoke.TRAIN.read_bytes())
    monkeypatch.setattr(smoke, "verified_data", lambda: (rows, {"train_sha256": smoke.TRAIN_SHA}))
    result = smoke.preflight()
    assert result["status"] == smoke.DATA
    assert result["deficient_strata"] == {"unknown_unresolved_reference": 0, "unknown_ambiguous_version": 0}
    assert result["blocker"] == "fixed_strata_incomplete_or_duplicate"
    assert result["model_loads"] == result["live_invocations"] == result["optimizer_steps"] == 0
    assert result["checkpoint_created"] is False
    assert "subset_manifest" not in result
    assert result["data_identity_before"] == result["data_identity_after"]
    unsigned = dict(result)
    assert unsigned.pop("canonical_report_sha256") == smoke.canonical_hash(unsigned)


def test_verifier_failure_stops_before_selection(monkeypatch):
    def fail():
        raise smoke.DataBoundaryError("corpus_or_seal_verification_failed")
    monkeypatch.setattr(smoke, "verified_data", fail)
    monkeypatch.setattr(smoke, "select_subset", lambda _rows: pytest.fail("selection must not run"))
    assert smoke.preflight()["blocker"] == "corpus_or_seal_verification_failed"


def test_pre_post_identity_mutation_fails_closed(monkeypatch, synthetic_rows):
    values = iter([(synthetic_rows, {"hash": "before"}), (synthetic_rows, {"hash": "after"})])
    monkeypatch.setattr(smoke, "verified_data", lambda: next(values))
    result = smoke.preflight()
    assert result["status"] == smoke.DATA and result["blocker"] == "frozen_data_mutated"


def test_canonical_log_hash_deterministic():
    first = {"schema": "test", "counts": {"play": 16, "unknown": 16}, "live_invocations": 0}
    second = dict(reversed(list(first.items())))
    assert smoke.canonical_bytes(first) == smoke.canonical_bytes(second)
    assert smoke.canonical_hash(first) == smoke.canonical_hash(json.loads(smoke.canonical_bytes(second)))
    with pytest.raises(ValueError):
        smoke.canonical_hash({"loss": float("nan")})


@pytest.mark.parametrize("flag", list(smoke.AUTHORITY_FLAGS))
def test_authority_environment_stays_false(monkeypatch, flag):
    manifest = {"seal_manifest_sha256": smoke.SEAL_SHA, "sealed_row_count": 600,
                "sealed_group_count": 100, "final_split_assigned": True, "held_out_sealed": True,
                **smoke.AUTHORITY_FLAGS}
    monkeypatch.setattr(smoke.seal, "verify_seal", lambda: manifest)
    monkeypatch.setenv(flag, "true")
    with pytest.raises(smoke.DataBoundaryError, match="authority_flag_changed"):
        smoke.verified_data()
