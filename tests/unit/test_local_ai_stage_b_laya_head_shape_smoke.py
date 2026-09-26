"""Offline Stage B Laya shape boundaries; no GPU or model weights."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import local_ai_stage_b_laya_adapter as adapter  # noqa: E402
import local_ai_stage_b_laya_forward_backward_smoke as smoke  # noqa: E402


class CharTokenizer:
    cls_token_id = 101
    sep_token_id = 102
    mask_token_id = 103
    pad_token_id = 0
    mask_token = "[MASK]"

    def __call__(self, text: str, *, add_special_tokens: bool = False,
                 return_offsets_mapping: bool = False) -> dict:
        assert add_special_tokens is False
        out = {"input_ids": [ord(ch) + 200 for ch in text]}
        if return_offsets_mapping:
            out["offset_mapping"] = [(i, i + 1) for i in range(len(text))]
        return out


def test_fixture_identity_slices_and_no_forbidden_fields() -> None:
    rows = adapter.load_fixture()
    assert len(rows) == len({row["row_id"] for row in rows}) == 64
    assert hashlib.sha256(adapter.FIXTURE.read_bytes()).hexdigest() == smoke.FIXTURE_SHA
    assert [sum(row["row_id"] in {f"smoke-{n:03d}" for n in range(i, i + 8)} for row in rows)
            for i in range(1, 65, 8)] == [8] * 8
    assert all(set(row) == adapter.FIELDS for row in rows)
    assert all(row["track_span"] is not None for row in rows[:32])
    assert all(all(row[k] is None for k in adapter.SLOT_TAGS) for row in rows[32:])
    assert all(not adapter.FORBIDDEN_TEXT.search(row["utterance"]) for row in rows)


def test_fixture_rejects_bad_span_overlap_missing_track_and_unknown_slot(tmp_path: Path) -> None:
    rows = adapter.load_fixture()
    for index, field, value, reason in (
        (0, "track_span", None, "fixture_track_presence"),
        (16, "artist_span", rows[16]["track_span"], "fixture_span_overlap"),
        (32, "track_span", {"start": 0, "end": 1}, "fixture_track_presence"),
        (0, "utterance", "https://example.com", "fixture_utterance"),
    ):
        broken = copy.deepcopy(rows)
        broken[index][field] = value
        path = tmp_path / "broken.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in broken), encoding="utf-8")
        with pytest.raises(adapter.ShapeError, match=reason):
            adapter.load_fixture(path)


def test_masks_labels_and_deterministic_render() -> None:
    tok = CharTokenizer()
    rows = adapter.load_fixture()
    for row in rows:
        item = adapter.render_row(tok, row)
        assert item == adapter.render_row(tok, row)
        assert len(item["input_ids"]) == len(item["user_state_mask"]) == len(item["bio_labels"])
        assert all(item["bio_labels"][i] == -100 and item["token_offsets"][i] is None
                   for i, active in enumerate(item["user_state_mask"]) if not active)
        assert not item["user_state_mask"][0] and not item["user_state_mask"][-1]
        assert all(not item["user_state_mask"][i] for i in item["marker_pos"])
        assert all(item["bio_labels"][i] in range(7)
                   for i, active in enumerate(item["user_state_mask"]) if active)
        if row["expected_intent"] == "play":
            assert 1 in item["bio_labels"]
            assert (3 in item["bio_labels"]) == (row["artist_span"] is not None)
            assert (5 in item["bio_labels"]) == (row["album_span"] is not None)
        else:
            assert set(item["bio_labels"]) <= {-100, 0}


def test_renderer_divergence_and_truncation_fail_closed() -> None:
    tok = CharTokenizer()
    row = adapter.load_fixture()[0]
    with pytest.raises(adapter.ShapeError, match="required_state_truncated"):
        adapter.render_row(tok, row, max_len=20)
    with pytest.raises(adapter.ShapeError, match="STOP_LAYA_RENDERING_DIVERGENCE"):
        adapter.validate_rendering(tok, lambda *args: ([1], [2]), [row])


def test_batch_padding_excludes_state_and_labels() -> None:
    import torch
    tok = CharTokenizer()
    rows = adapter.load_fixture()
    items = [adapter.render_row(tok, rows[i]) for i in (0, 24)]
    batch = smoke.batch_tensors(items, tok.pad_token_id, "cpu", torch)
    assert tuple(batch["input_ids"].shape)[0] == 2
    padding = batch["attention_mask"] == 0
    assert bool(padding.any())
    assert not bool(batch["user_state_mask"][padding].any())
    assert bool((batch["bio_labels"][padding] == -100).all())


def test_null_postprocessing() -> None:
    utterance = "Play invented tune"
    track = {"start": 5, "end": len(utterance)}
    assert adapter.safe_slots("unknown", utterance, {"track": track}) == {
        "intent": "unknown", "track": None, "artist": None, "album": None}
    assert adapter.safe_slots("play", utterance, {"track": None})["intent"] == "unknown"
    assert adapter.safe_slots("play", utterance, {"track": {"start": 999, "end": 1000}})["intent"] == "unknown"
    assert adapter.safe_slots("play", utterance, {"track": {"start": 4, "end": 5}})["intent"] == "unknown"
    assert adapter.safe_slots("play", utterance, {"track": track})["track"] == "invented tune"


def test_shape_contract_and_gradient_checks_on_cpu() -> None:
    import torch
    shapes = {"typed_logits": (8, 2), "action_logits": (8, 2),
              "hidden_states": (8, 36, 768), "span_logits": (8, 36, 7),
              "validity_logits": (8,), "user_state_mask": (8, 36)}
    assert smoke.shape_contract(shapes) == (36, 768)
    for key, bad in (("typed_logits", (8, 3)), ("span_logits", (8, 35, 7)),
                     ("validity_logits", (8, 2))):
        changed = dict(shapes, **{key: bad})
        with pytest.raises(smoke.pinned.GateError):
            smoke.shape_contract(changed)
    p = torch.nn.Parameter(torch.ones(2))
    with pytest.raises(smoke.pinned.GateError, match="required_gradient_absent"):
        smoke.gradient_norm([p], "cpu", torch)
    p.grad = torch.tensor([1.0, 0.0])
    assert smoke.gradient_norm([p], "cpu", torch) == 1.0
    p.grad = torch.tensor([float("nan"), 0.0])
    with pytest.raises(smoke.pinned.GateError, match="gradient_nonfinite"):
        smoke.gradient_norm([p], "cpu", torch)
    with pytest.raises(smoke.pinned.GateError, match="output_nonfinite_or_wrong_device"):
        smoke.require_finite_tensors({"typed": torch.tensor([float("inf")])}, "cpu", torch)


def test_encoder_freeze_and_three_head_backward_on_cpu() -> None:
    import torch
    encoder = torch.nn.Linear(4, 4)
    typed = torch.nn.Linear(4, 2)
    span = torch.nn.Linear(4, 7)
    validity = torch.nn.Linear(4, 1)
    smoke.freeze_encoder(encoder)
    hidden = encoder(torch.ones(8, 3, 4))
    loss = (torch.nn.functional.cross_entropy(typed(hidden[:, 0]), torch.zeros(8, dtype=torch.long))
            + torch.nn.functional.cross_entropy(span(hidden).reshape(-1, 7), torch.zeros(24, dtype=torch.long))
            + torch.nn.functional.binary_cross_entropy_with_logits(validity(hidden[:, 0]).squeeze(-1), torch.ones(8)))
    loss.backward()
    smoke.require_no_encoder_grads(encoder)
    assert smoke.gradient_norm(typed.parameters(), "cpu", torch) > 0
    assert smoke.gradient_norm(span.parameters(), "cpu", torch) > 0
    assert smoke.gradient_norm(validity.parameters(), "cpu", torch) > 0
    next(encoder.parameters()).grad = torch.ones_like(next(encoder.parameters()))
    with pytest.raises(smoke.pinned.GateError, match="encoder_gradient_present"):
        smoke.require_no_encoder_grads(encoder)


def test_parent_raw_bytes_utf8_and_blocker_preservation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke.pinned, "PYTHON", Path(sys.executable))
    monkeypatch.setattr(smoke, "verified_seal", lambda: {"seal_manifest_sha256": smoke.pinned.SEAL_SHA})
    def runner(command, **kwargs):
        assert command[1:4] == ["-B", "-X", "utf8"]
        assert kwargs["text"] is False and kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        payload = {"status": smoke.BLOCK, "blocker": "exact_blocker"}
        return subprocess.CompletedProcess(command, 1,
            (smoke.RESULT_PREFIX + json.dumps(payload)).encode(), b"non-utf8:\xff")
    result = smoke.parent(runner)
    assert result["blocker"] == "exact_blocker" and result["child_returncode"] == 1


def test_identity_and_seal_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke, "verify_seal", lambda: {
        "seal_manifest_sha256": "wrong", "sealed_row_count": 600,
        "sealed_group_count": 100, "final_split_assigned": True, "held_out_sealed": True,
        **smoke.AUTHORITY_FLAGS})
    with pytest.raises(smoke.pinned.GateError, match="stage_b_seal_mismatch"):
        smoke.verified_seal()
    monkeypatch.setattr(smoke, "FIXTURE_SHA", "wrong")
    with pytest.raises(adapter.ShapeError, match="STOP_LAYA_SHAPE_FIXTURE_INVALID:fixture_identity_mismatch"):
        smoke.fixture_and_render(CharTokenizer(), None, {})


def test_no_optimizer_or_frozen_corpus_path_in_runner() -> None:
    source = Path(smoke.__file__).read_text(encoding="utf-8")
    assert "torch.optim" not in source and ".step(" not in source
    assert "artifacts/local_ai/stage_b/final_v1" not in source
    assert "held_out.jsonl" not in source and "ai_intent_cases.json" not in source
    assert "total.backward()" in source
