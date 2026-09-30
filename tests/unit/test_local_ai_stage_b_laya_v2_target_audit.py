"""No model/framework imports, backward, real hidden states or non-train rows."""
import ast
import copy
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace as N

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_laya_v2_target_audit as audit


@pytest.fixture(scope="module")
def frozen():
    return (audit.TRAIN.read_bytes(), audit.load_manifest("corpus_manifest.json"),
            audit.load_manifest("split_assignment.json"))


def test_exact_train_identity_groups_and_no_validation(frozen):
    raw, manifest, assignment = frozen
    rows = audit.verified_train(*frozen)
    assert hashlib.sha256(raw).hexdigest() == audit.TRAIN_SHA
    assert len(rows) == 1800 and len({r.source_group_id for r in rows}) == 300
    assert sum(r.ai_scope == "supported" for r in rows) == 1500
    assert sum(r.expected.intent == "spotify_play_track" for r in rows) == 900
    assert manifest["per_split_language_tag_counts"]["train"]["en"] == 0


@pytest.mark.parametrize("fault", ["sha", "count", "duplicate", "groups", "membership", "canonical"])
def test_train_identity_fails_closed(frozen, monkeypatch, fault):
    raw, manifest, assignment = copy.deepcopy(frozen)
    if fault == "sha":
        raw += b" "
    elif fault in ("count", "duplicate", "groups"):
        lines = raw.splitlines()
        if fault == "count": lines.pop()
        elif fault == "duplicate": lines[1] = lines[0]
        else:
            row = json.loads(lines[0]); row["source_group_id"] = "source-group-0001"
            lines[0] = json.dumps(row).encode()
        raw = b"\n".join(lines)
        monkeypatch.setattr(audit, "TRAIN_SHA", hashlib.sha256(raw).hexdigest())
    elif fault == "membership":
        entry = next(v for v in assignment["groups"].values() if v["state"] == "train")
        entry["candidate_ids"] = list(reversed(entry["candidate_ids"]))
    else:
        manifest["split_sha256"]["train"] = "0" * 64
    with pytest.raises(ValueError): audit.verified_train(raw, manifest, assignment)


def test_manifest_self_hash_is_required(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "TRAIN", tmp_path / "train.jsonl")
    (tmp_path / "corpus_manifest.json").write_text('{"manifest_sha256":"wrong"}')
    with pytest.raises(ValueError, match="manifest_identity"):
        audit.load_manifest("corpus_manifest.json")


def test_pool_only_user_state_and_equivalent_padding():
    hidden = [[999, -999], [1, 3], [3, 7], [float("nan"), float("inf")]]
    mask = [False, True, True, False]
    assert audit.masked_user_mean(hidden, mask) == [2, 5]
    assert audit.masked_user_mean(hidden, mask) == audit.masked_user_mean(hidden, mask)
    assert audit.masked_user_mean([[999, 999]] + hidden + [[-999, -999]], [False] + mask + [False]) == [2, 5]


@pytest.mark.parametrize("hidden,mask", [([], []), ([[1]], [False]), ([[1]], []),
    ([[1]], [1]), ([[1], [1, 2]], [True, False]), ([[float("nan")]], [True])])
def test_pool_rejects_empty_invalid_or_nonfinite(hidden, mask):
    with pytest.raises(ValueError): audit.masked_user_mean(hidden, mask)


def test_start_supervision_exposes_orphan_i_despite_token_average():
    # Invented [8 tokens, 7 labels] tensor. No corpus/tokenizer/model involved.
    good_o = [5, 0, 0, 0, 0, 0, 0]
    orphan = [0, -2, 4, -3, -3, -3, -3]
    logits = [good_o] * 7 + [orphan]
    labels = [0] * 7 + [1]
    mask = [True] * 8
    before = audit.objective_terms(logits, labels, mask)
    improved = copy.deepcopy(logits); improved[-1][1] += 1
    after = audit.objective_terms(improved, labels, mask)
    start_before = before["slot_start_terms"]["B-TRACK"]["positive"]
    start_after = after["slot_start_terms"]["B-TRACK"]["positive"]
    assert start_before["count"] == 1 and start_before["mean_loss"] > 5
    assert math.isclose(start_before["mean_loss"] - start_after["mean_loss"],
                        8 * (before["token_ce"] - after["token_ce"]), rel_tol=1e-12)
    # Finite difference shows start supervision responds without calling backward.
    assert start_after["mean_loss"] < start_before["mean_loss"]
    assert before["slot_start_terms"]["B-ARTIST"]["positive"] == {"count": 0, "mean_loss": None}
    assert before["slot_start_terms"]["B-TRACK"]["negative"]["count"] == 7


def test_false_b_predictions_have_negative_start_penalty():
    before = audit.objective_terms([[5, 0, 0, 0, 0, 0, 0]], [0], [True])
    after = audit.objective_terms([[0, 5, 0, 0, 0, 0, 0]], [0], [True])
    assert after["slot_start_terms"]["B-TRACK"]["negative"]["mean_loss"] > before["slot_start_terms"]["B-TRACK"]["negative"]["mean_loss"]


def test_objective_mask_padding_stability_no_weights_or_new_labels():
    row = [0, 1, 2, 3, 4, 5, 6]
    actual = audit.objective_terms([row], [1], [True])
    assert actual == audit.objective_terms([[float("nan")]*7, row, [100]*7], [-100, 1, -100], [False, True, False])
    assert actual == audit.objective_terms([[x + 1000 for x in row]], [1], [True])
    assert set(actual) == {"token_ce", "slot_start_terms", "user_tokens"}
    assert set(actual["slot_start_terms"]) == {"B-TRACK", "B-ARTIST", "B-ALBUM"}


@pytest.mark.parametrize("logits,labels,mask", [([], [], []), ([[0]*7], [7], [True]),
    ([[0]*6], [1], [True]), ([[float("inf")]*7], [1], [True]), ([[0]*7], [1], [False]),
    ([[0]*7], [True], [True])])
def test_objective_invalid_inputs_fail_closed(logits, labels, mask):
    with pytest.raises(ValueError): audit.objective_terms(logits, labels, mask)


class FakeTokenizer:
    """Invented character encoder for renderer target mechanics only."""
    cls_token_id, sep_token_id, mask_token_id, pad_token_id = 1, 2, 3, 0
    mask_token = "<mask>"

    def __call__(self, text, **kwargs):
        value = {"input_ids": [ord(x) + 10 for x in text]}
        if kwargs.get("return_offsets_mapping"):
            value["offset_mapping"] = [(i, i + 1) for i in range(len(text))]
        return value


def synthetic_rows():
    span = lambda a, b: N(start=a, end=b)
    return [N(ai_scope="supported", utterance="abcdef", expected=N(intent="spotify_play_track",
        track=span(0, 2), artist=span(2, 3), album=span(4, 6))),
        N(ai_scope="supported", utterance="nothing", expected=N(intent="unknown", track=None, artist=None, album=None))]


def test_target_copy_mapping_span_counts_and_start_inside_ratio():
    summary = audit.summarize(synthetic_rows(), FakeTokenizer(), {"max_len": 512, "head_max_len": 192})
    assert summary["target_pairs"] == {"intent=0,validity=1": 1, "intent=1,validity=0": 1}
    assert summary["bio_token_counts"] == dict(zip(audit.LABELS, [8, 1, 1, 1, 0, 1, 1]))
    assert summary["span_token_lengths"]["track"]["begin_to_inside_ratio"] == 1
    assert summary["span_token_lengths"]["artist"]["one_token_rows"] == 1
    assert summary["span_token_lengths"]["artist"]["begin_to_inside_ratio"] is None
    assert summary["span_token_lengths"]["album"]["multi_token_rows"] == 1
    assert audit.canonical_hash(summary) == audit.canonical_hash(json.loads(json.dumps(summary)))


def test_blocked_rows_never_render():
    rows = synthetic_rows(); rows[0].ai_scope = "safety_only"
    with pytest.raises(ValueError, match="blocked_row_rendering"):
        audit.summarize(rows, N(), {})


@pytest.mark.parametrize("relative", ["artifacts/local_ai/stage_b/final_v1/validation.jsonl",
    "artifacts/local_ai/stage_b/final_v1/held_out.jsonl", "artifacts/local_ai/stage_b/sealed_v1/held_out.jsonl",
    "tests/fixtures/ai_intent_cases.json", "external/final.pt", "external/model.safetensors"])
def test_read_guard_denies_nontrain_inputs(relative):
    with pytest.raises(ValueError):
        audit.read_guard(set())("open", (str(audit.ROOT / relative), "r", os.O_RDONLY))


def test_guard_records_train_and_denies_writes_network_and_framework():
    opened = set(); guard = audit.read_guard(opened)
    guard("open", (str(audit.TRAIN), "rb", os.O_RDONLY))
    assert opened == {"train"}
    with pytest.raises(ValueError): guard("open", (str(audit.TRAIN), "w", os.O_WRONLY))
    with pytest.raises(PermissionError): guard("socket.connect", ())
    with pytest.raises(PermissionError): guard("import", ("torch",))


def test_source_has_no_training_model_or_checkpoint_calls():
    source = Path(audit.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any(isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in ("torch", "laya") for n in imports)
    calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
    assert not any(x.endswith((".backward", ".step", ".load")) for x in calls)
    assert "AutoTokenizer.from_pretrained" in calls
    assert all(value is False for value in audit.FLAGS.values())
