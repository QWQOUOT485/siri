"""Train-only tokenizer target audit and synthetic CPU math; no model execution."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import local_ai_stage_b_corpus as corpus
import local_ai_stage_b_laya_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
BASE = "b0491a5f76ca0b614d3718edbd887717b2c32b28"
TRAIN = ROOT / "artifacts/local_ai/stage_b/final_v1/train.jsonl"
TRAIN_SHA = "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2"
MANIFESTS = {
    "corpus_manifest.json": ("manifest_sha256", "297c1bdc79243944af6d2b866cd89faf1afc0e6b47048c913ced8f027fa3a45c"),
    "split_assignment.json": ("split_assignment_sha256", "84e8fe440674a0e5af785586fdde893b5e48e020583a8269f7ae27870201be37"),
}
MODEL = Path(r"D:\ai\ai\laya")
TOKENIZER_SHA = {
    "tokenizer/tokenizer.json": "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
    "tokenizer/tokenizer_config.json": "2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f",
    "rl_agent_config.json": "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6",
}
REVISION = "052592a15d198d9ad47da779604259b10b47b7aa"
LABELS = ("O", "B-TRACK", "I-TRACK", "B-ARTIST", "I-ARTIST", "B-ALBUM", "I-ALBUM")
FLAGS = dict.fromkeys(("training_authorized", "model_compute_authorized", "semantic_memory_enabled",
    "local_ai_fallback_approved", "LOCAL_SEMANTIC_MEMORY_ENABLED", "LOCAL_AI_FALLBACK_APPROVED"), False)
SOURCES = ("local_ai_stage_b_corpus.py", "local_ai_stage_b_laya_adapter.py",
    "local_ai_stage_b_laya_small_adaptation.py", "local_ai_stage_b_laya_training_pipeline_smoke.py",
    "local_ai_stage_b_laya_span_decoder.py", "local_ai_stage_b_laya_v2_target_audit.py")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value):
    return digest(corpus.canonical_json(value).encode("utf-8"))


def verified_train(raw, manifest, assignment):
    require(digest(raw) == TRAIN_SHA, "train_sha_mismatch")
    lines = raw.decode("utf-8", "strict").splitlines()
    require(len(lines) == 1800, "train_row_count")
    rows = [corpus.StageBRecord.from_mapping(json.loads(line)) for line in lines]
    require(len({r.case_id for r in rows}) == 1800, "duplicate_case_id")
    groups = defaultdict(list)
    for row in rows:
        groups[row.source_group_id].append(row.case_id)
    require(len(groups) == 300 and all(len(ids) == 6 for ids in groups.values()), "whole_group_count")
    assigned = {gid: value for gid, value in assignment["groups"].items() if value["state"] == "train"}
    require(set(groups) == set(assigned), "train_group_assignment")
    for gid, ids in groups.items():
        require(ids == assigned[gid]["candidate_ids"] and canonical_hash(ids) == assigned[gid]["membership_sha256"],
                "whole_group_membership")
    canonical_rows = corpus._canonical_records(rows)
    require(canonical_hash(canonical_rows) == manifest["split_sha256"]["train"], "canonical_train_identity")
    require(manifest["per_split_row_counts"]["train"] == len(rows), "manifest_train_count")
    return rows


def load_manifest(name):
    key, expected = MANIFESTS[name]
    value = json.loads((TRAIN.parent / name).read_bytes())
    require(value.pop(key) == expected == canonical_hash(value), "manifest_identity")
    return value


def masked_user_mean(hidden, mask):
    """Rectangular CPU numeric tensor [tokens, features]; no framework/model import."""
    require(bool(hidden) and len(hidden) == len(mask) and all(type(x) is bool for x in mask), "pool_shape_or_mask")
    width = len(hidden[0])
    require(width > 0 and all(len(row) == width for row in hidden), "pool_rectangular")
    selected = [row for row, inside in zip(hidden, mask) if inside]
    require(bool(selected), "empty_user_state_mask")
    require(all(type(x) in (int, float) and math.isfinite(x) for row in selected for x in row), "pool_nonfinite")
    result = [math.fsum(row[j] for row in selected) / len(selected) for j in range(width)]
    require(all(math.isfinite(x) for x in result), "pool_nonfinite")
    return result


def logsumexp(values):
    top = max(values)
    return top + math.log(math.fsum(math.exp(x - top) for x in values))


def objective_terms(logits, labels, mask):
    """Unweighted diagnostic terms; no total/coefficient or training implementation.

    Slot-start probability is the B label probability from the SAME seven logits.
    Positive and negative strata are reduced separately, never silently dropped.
    """
    require(len(logits) == len(labels) == len(mask) and all(type(x) is bool for x in mask), "objective_shape")
    selected = [(row, tag) for row, tag, inside in zip(logits, labels, mask) if inside]
    require(bool(selected), "empty_user_state_mask")
    require(all(len(row) == 7 and all(type(x) in (int, float) and math.isfinite(x) for x in row)
        and type(tag) is int and tag in range(7) for row, tag in selected), "objective_values")
    selected = [([x - max(row) for x in row], tag) for row, tag in selected]
    plain = math.fsum(logsumexp(row) - row[tag] for row, tag in selected) / len(selected)
    starts = {}
    for begin in (1, 3, 5):
        strata = {"positive": [], "negative": []}
        for row, tag in selected:
            loss = (logsumexp(row) - row[begin] if tag == begin else
                    logsumexp(row) - logsumexp([x for i, x in enumerate(row) if i != begin]))
            strata["positive" if tag == begin else "negative"].append(loss)
        starts[LABELS[begin]] = {key: {"count": len(values),
            "mean_loss": math.fsum(values) / len(values) if values else None}
            for key, values in strata.items()}
    return {"token_ce": plain, "slot_start_terms": starts, "user_tokens": len(selected)}


def length_summary(lengths):
    counts = Counter(lengths)
    return {"spans": len(lengths), "one_token_rows": counts[1],
        "multi_token_rows": sum(n for length, n in counts.items() if length > 1),
        "mean": math.fsum(lengths) / len(lengths) if lengths else None,
        "min": min(lengths) if lengths else None, "max": max(lengths) if lengths else None,
        "histogram": {str(k): v for k, v in sorted(counts.items())},
        "begin_to_inside_ratio": len(lengths) / sum(x - 1 for x in lengths) if sum(x - 1 for x in lengths) else None}


def summarize(rows, tokenizer, config):
    totals = Counter()
    lengths = {slot: [] for slot in ("track", "artist", "album")}
    relations = Counter()
    for row in rows:
        require(row.ai_scope == "supported", "blocked_row_rendering")
        item = {"utterance": row.utterance,
            "expected_intent": "play" if row.expected.intent == "spotify_play_track" else "unknown",
            **{slot + "_span": None if (span := getattr(row.expected, slot)) is None else
               {"start": span.start, "end": span.end} for slot in lengths}}
        rendered = adapter.render_row(tokenizer, item, max_len=config["max_len"], head_max_len=config["head_max_len"])
        mask = rendered["user_state_mask"]
        labels = [tag for tag, inside in zip(rendered["bio_labels"], mask) if inside]
        require(all(tag == -100 for tag, inside in zip(rendered["bio_labels"], mask) if not inside), "nonuser_target")
        require(rendered["validity_label"] == 1 - rendered["intent_label"], "validity_target_relation")
        relations[f"intent={rendered['intent_label']},validity={rendered['validity_label']}"] += 1
        totals.update(labels)
        for slot, (begin, inner) in adapter.SLOT_TAGS.items():
            slot = slot.removesuffix("_span")
            n = labels.count(begin) + labels.count(inner)
            require(labels.count(begin) == int(getattr(row.expected, slot) is not None), "begin_span_count")
            if n:
                lengths[slot].append(n)
    plays = sum(r.expected.intent == "spotify_play_track" for r in rows)
    return {"rows": len(rows), "play": plays, "unknown": len(rows) - plays,
        "play_fraction": plays / len(rows) if rows else None,
        "target_pairs": dict(relations), "validity_is_one_minus_intent_label": True,
        "user_state_tokens": sum(totals.values()), "bio_token_counts": {label: totals[i] for i, label in enumerate(LABELS)},
        "span_token_lengths": {slot: length_summary(values) for slot, values in lengths.items()}}


def tokenizer_identity():
    observed = {}
    for name, expected in TOKENIZER_SHA.items():
        path = MODEL / name
        require(path.is_file() and not path.is_symlink(), "tokenizer_redirected_or_missing")
        require(digest(path.read_bytes()) == expected, "tokenizer_identity")
        metadata = MODEL / ".cache/huggingface/download" / (name + ".metadata")
        require(metadata.read_bytes().splitlines()[0].decode("ascii") == REVISION, "tokenizer_revision")
        observed[name] = expected
    return {"revision": REVISION, "files": observed, "weight_files_opened": False}


def read_guard(opened):
    allowed = {TRAIN.resolve(): "train", **{(TRAIN.parent / name).resolve(): name for name in MANIFESTS}}
    def guard(event, args):
        if event in ("socket.connect", "socket.getaddrinfo", "subprocess.Popen"):
            raise PermissionError("audit_network_or_subprocess_forbidden")
        if event == "import" and args[0].split(".")[0] in ("torch", "laya", "tensorflow", "jax"):
            raise PermissionError("audit_model_framework_import_forbidden")
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        protected = path.is_relative_to(ROOT / "artifacts") or path.is_relative_to(ROOT / "tests/fixtures")
        require(path.suffix.lower() not in (".pt", ".pth", ".safetensors", ".ckpt", ".bin"), "model_or_checkpoint_read_forbidden")
        require(not protected or path in allowed, "unapproved_corpus_read")
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(x in mode for x in "wax+")) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        require(not writing, "audit_write_forbidden")
        if path in allowed:
            opened.add(allowed[path])
    return guard


def run_audit():
    require(sys.flags.utf8_mode == 1 and sys.dont_write_bytecode, "utf8_no_bytecode_required")
    require(all(os.environ.get(key, "false").casefold() == "false" for key in FLAGS), "authority_changed")
    require(all(os.environ.get(key) == "1" for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")), "offline_required")
    require(os.environ.get("USE_TORCH") == os.environ.get("USE_TF") == os.environ.get("USE_FLAX") == "0", "frameworks_must_be_disabled")
    opened = set()
    sys.addaudithook(read_guard(opened))
    manifest, assignment = (load_manifest(name) for name in MANIFESTS)
    raw = TRAIN.read_bytes()
    rows = verified_train(raw, manifest, assignment)
    identity = tokenizer_identity()
    source_hashes = {name: digest((ROOT / "scripts" / name).read_bytes()) for name in SOURCES}
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL / "tokenizer"), local_files_only=True)
    config = json.loads((MODEL / "rl_agent_config.json").read_bytes())
    eligible = [row for row in rows if row.ai_scope == "supported"]
    result = {"schema": "laya-v2-train-target-audit-v1", "status": "LAYA_V2_PROTOCOL_TARGET_AUDIT_READY",
        "repo_base": BASE, "train_sha256": TRAIN_SHA, "train_rows": len(rows), "train_groups": 300,
        "whole_group_identity_verified": True, "blocked_before_rendering": len(rows) - len(eligible),
        "authority_flags": FLAGS, "tokenizer_identity": identity, "source_sha256": source_hashes,
        "manifest_self_sha256": {name: value[1] for name, value in MANIFESTS.items()},
        "supported": summarize(eligible, tokenizer, config),
        "by_language": {key: summarize([r for r in eligible if r.language_tag == key], tokenizer, config)
            for key in sorted({r.language_tag for r in eligible})},
        "by_template_family": {key: summarize([r for r in eligible if r.template_family == key], tokenizer, config)
            for key in sorted({r.template_family for r in eligible})},
        "language_coverage_manifest_only": {"source": "final_v1/corpus_manifest.json",
            "train": manifest["per_split_language_tag_counts"]["train"],
            "validation": manifest["per_split_language_tag_counts"]["validation"],
            "validation_rows_opened": False},
        "selected_objective": "seven-class-token-ce-plus-stratified-slot-start-vs-rest-bce-shared-logits",
        "selected_validity_representation": "user-state-only-masked-arithmetic-mean",
        "numeric_hyperparameters_selected": False}
    require(TRAIN.read_bytes() == raw and tokenizer_identity() == identity, "train_or_tokenizer_mutated")
    require(source_hashes == {name: digest((ROOT / "scripts" / name).read_bytes()) for name in SOURCES}, "source_mutated")
    for name in MANIFESTS:
        load_manifest(name)
    require(not any(name in sys.modules for name in ("torch", "laya", "tensorflow", "jax")), "model_framework_imported")
    result["process_boundary"] = {"opened_data_inputs": sorted(opened), "tokenizer_only_cpu": True,
        "model_loaded": False, "checkpoint_loaded": False, "gpu_used": False, "training_performed": False,
        "validation_rows_opened": False, "held_out_rows_opened": False, "stage_a_rows_opened": False,
        "frameworks_imported": False, "before_after_identities_equal": True}
    result["canonical_result_sha256"] = canonical_hash(result)
    return result


if __name__ == "__main__":
    print(json.dumps(run_audit(), ensure_ascii=False, sort_keys=True, indent=2))
