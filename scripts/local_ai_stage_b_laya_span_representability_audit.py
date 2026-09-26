"""Tokenizer/label/offset structural audit. Never changes rendering or decoding."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import local_ai_stage_b_corpus as corpus
import local_ai_stage_b_laya_adapter as adapter
from local_ai_stage_b_laya_small_adaptation import decode as strict_decode

BASE = "7c55924c7ae5f90f519c3d73889b04d0c430423b"
ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(r"D:\ai\venvs\siri-stage-b-rocm10-gfx1201\Scripts\python.exe")
ARTIFACT = Path(r"D:\ai\ai\laya")
REVISION = "052592a15d198d9ad47da779604259b10b47b7aa"
REVIEWED_AGGREGATE = "eee3b3f039903321cab43a4fc2238af9a0d652920c698b69838dfd5458969dcf"
TOKENIZER_HASHES = {
    "tokenizer/tokenizer.json": "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f",
    "tokenizer/tokenizer_config.json": "2c0c4d82d4b4bc6b4ac40b2375e067a1645f78b381a9774248d47915f33d751f",
    "rl_agent_config.json": "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6"}
SPLITS = {"train": (1800, 900, "54624942de9b1011404000bff2033d726a0a3934c4f515914ce31764648fc1d2"),
          "validation": (600, 300, "297140d7f4b63e2ca326a5f323672a631d1585fb6a970e68021c2c554fefa23a")}
RESULT79 = ROOT / "docs/local_ai/stage_b/evidence/LAYA_SMALL_ADAPTATION_RESULT_2026-09-26.json"
RESULT79_HASH = "4836d1fa2bf5a499cd8f4dfed9d23fd07620af4976963aecb4c397f148de7bd8"
FLAGS = dict.fromkeys(("training_authorized", "model_compute_authorized", "semantic_memory_enabled",
    "local_ai_fallback_approved", "LOCAL_SEMANTIC_MEMORY_ENABLED", "LOCAL_AI_FALLBACK_APPROVED"), False)
SLOTS = ("track", "artist", "album")
WHITESPACE = ("leading_whitespace_only", "trailing_whitespace_only", "both_whitespace_only",
              "non_whitespace_boundary_error", "missing_or_multiple_span")
TRACK_STOP = "STOP_LAYA_SPAN_REPRESENTATION_TRACK_BELOW_GATE"
TARGET_STOP = "STOP_LAYA_SPAN_TARGET_CONSTRUCTION_BELOW_GATE"
PASS = "LAYA_SPAN_REPRESENTABILITY_AUDIT_PASSED"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def split_path(name: str) -> Path:
    require(name in SPLITS, "split_not_authorized")
    return ROOT / "artifacts/local_ai/stage_b/final_v1" / (name + ".jsonl")


def parse_split(name: str, raw: bytes) -> list[Any]:
    require(name in SPLITS, "split_not_authorized")
    count, play_count, digest = SPLITS[name]
    require(hashlib.sha256(raw).hexdigest() == digest, name + "_sha_mismatch")
    lines = raw.decode("utf-8", "strict").splitlines()
    require(len(lines) == count, name + "_row_count")
    rows = [corpus.StageBRecord.from_mapping(json.loads(line)) for line in lines]
    require(len({r.case_id for r in rows}) == count, "duplicate_case_id")
    play = [r for r in rows if r.ai_scope == "supported" and r.expected.intent == "spotify_play_track"]
    require(len(play) == play_count, name + "_play_count")
    for slot in ("artist", "album"):
        require(sum(getattr(r.expected, slot) is not None for r in play)
                == sum(r.optional_slot_status[slot] == "present" for r in play), "slot_parser_disagreement")
    if name == "validation":
        require(sum(r.expected.artist is not None for r in play) == 126
                and sum(r.expected.album is not None for r in play) == 204, "validation_slot_denominators")
    return rows


def read_guard(opened: set[str], denied: list[str]):
    """Audit-process read gate; never installed into the general pytest process."""
    allowed = {str(split_path(name).resolve()).casefold(): name for name in SPLITS}
    artifact_root = str((ROOT / "artifacts").resolve()).casefold() + os.sep
    fixtures = str((ROOT / "tests/fixtures").resolve()).casefold() + os.sep
    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event in ("socket.connect", "socket.getaddrinfo"):
            denied.append("network")
            raise PermissionError("audit_network_forbidden")
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        key = str(path).casefold()
        protected = key.startswith((artifact_root, fixtures)) or path.name.casefold() in ("held_out.jsonl", "ai_intent_cases.json")
        binary = path.suffix.casefold() in (".pt", ".pth", ".safetensors", ".ckpt", ".bin")
        if binary or (protected and key not in allowed):
            denied.append("protected_or_weight_file")
            raise PermissionError("audit_file_forbidden")
        if key in allowed:
            mode = args[1] if len(args) > 1 else "r"
            require(mode is None or isinstance(mode, str) and not any(c in mode for c in "wax+"), "frozen_write_forbidden")
            opened.add(allowed[key])
    return guard


def tokenizer_identity() -> dict[str, Any]:
    observed = {}
    for name, digest in TOKENIZER_HASHES.items():
        path = ARTIFACT / name
        require(path.is_file() and not path.is_symlink(), "tokenizer_missing_or_redirected")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, "tokenizer_file_sha_mismatch")
        metadata = ARTIFACT / ".cache/huggingface/download" / (name + ".metadata")
        require(metadata.read_bytes().splitlines()[0].decode("ascii") == REVISION, "tokenizer_revision_mismatch")
        observed[name] = {"sha256": digest, "size_bytes": len(raw)}
    return {"revision": REVISION, "verified_local_files": observed,
            "reviewed_full_model_aggregate_sha256": REVIEWED_AGGREGATE,
            "full_model_aggregate_recomputed": False, "weight_files_opened": False}


def load_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(ARTIFACT / "tokenizer"), local_files_only=True)


def raw_span(span: Any) -> dict[str, int] | None:
    return None if span is None else {"start": span.start, "end": span.end}


def render(row: Any, tokenizer: Any, config: dict[str, Any]) -> dict[str, Any]:
    require(row.ai_scope == "supported", "blocked_row_not_rendered")
    item = {"row_id": row.case_id, "utterance": row.utterance, "language": row.language_tag,
        "expected_intent": "play" if row.expected.intent == "spotify_play_track" else "unknown",
        **{slot + "_span": raw_span(getattr(row.expected, slot)) for slot in SLOTS}}
    return adapter.render_row(tokenizer, item, max_len=config["max_len"], head_max_len=config["head_max_len"])


def any_interval(gold: dict[str, int], mask: list[bool], offsets: list[Any], length: int) -> list[int] | None:
    """Find an exact whole-token interval; no slicing, trimming or label assumptions."""
    require(len(mask) == len(offsets), "offset_mask_length")
    for i in range(len(mask)):
        if (not mask[i] or not isinstance(offsets[i], (tuple, list)) or len(offsets[i]) != 2
                or any(type(v) is not int for v in offsets[i]) or offsets[i][0] != gold["start"]):
            continue
        previous_end = gold["start"]
        for j in range(i, len(mask)):
            pair = offsets[j]
            if (not mask[j] or not isinstance(pair, (tuple, list)) or len(pair) != 2
                    or any(type(v) is not int for v in pair)
                    or not 0 <= pair[0] < pair[1] <= length or pair[0] < previous_end):
                break
            previous_end = pair[1]
            if pair[1] == gold["end"]:
                return [i, j]
            if pair[1] > gold["end"]:
                break
    return None


def classify(current: dict[str, int] | None, gold: dict[str, int], interval: Any) -> str:
    if current == gold:
        require(interval is not None, "exact_target_without_token_interval")
        return "A"
    return "B" if interval is not None else "C"


def whitespace_kind(text: str, current: dict[str, int] | None, gold: dict[str, int]) -> str:
    if current is None:
        return "missing_or_multiple_span"
    a, b = current["start"], current["end"]
    if not 0 <= a < b <= len(text):
        return "missing_or_multiple_span"
    if current == gold:
        return "exact"
    left, right = a, b
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if (left, right) != (gold["start"], gold["end"]):
        return "non_whitespace_boundary_error"
    return "both_whitespace_only" if left != a and right != b else "leading_whitespace_only" if left != a else "trailing_whitespace_only"


def audit_split(rows: list[Any], tokenizer: Any, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    stats = {slot: {"denominator": 0, "categories": dict.fromkeys("ABC", 0),
        "whitespace_mismatches": dict.fromkeys(WHITESPACE, 0),
        "boundary_alignment": dict.fromkeys(("first_token_start_exact", "last_token_end_exact", "both_boundaries_exact"), 0),
        "target_boundaries": dict.fromkeys(("exact_boundary", "first_begins_before", "last_ends_after", "both", "other"), 0),
        "examples": {}} for slot in SLOTS}
    details = {}
    unknown_checked = blocked = 0
    for row in rows:
        if row.ai_scope != "supported":
            require(all(getattr(row.expected, slot) is None for slot in SLOTS), "blocked_target_slots")
            blocked += 1
            continue
        item = render(row, tokenizer, config)
        if row.expected.intent == "unknown":
            require(set(item["bio_labels"]) <= {-100, 0}, "unknown_slot_target")
            unknown_checked += 1
            continue
        labels = [tag if inside else 0 for tag, inside in zip(item["bio_labels"], item["user_state_mask"])]
        decoded = strict_decode(0, 1.0, labels, item["user_state_mask"], item["token_offsets"], row.utterance)
        details[row.case_id] = {}
        for slot in SLOTS:
            gold = raw_span(getattr(row.expected, slot))
            if gold is None:
                continue
            current = decoded[slot]
            interval = any_interval(gold, item["user_state_mask"], item["token_offsets"], len(row.utterance))
            category = classify(current, gold, interval)
            diagnostic = whitespace_kind(row.utterance, current, gold)
            tags = adapter.SLOT_TAGS[slot + "_span"]
            target = [i for i, label in enumerate(item["bio_labels"]) if label in tags]
            require(bool(target), "present_slot_target_missing")
            first = item["token_offsets"][target[0]][0]
            last = item["token_offsets"][target[-1]][1]
            first_exact, last_exact = first == gold["start"], last == gold["end"]
            before, after = first < gold["start"], last > gold["end"]
            boundary = ("exact_boundary" if first_exact and last_exact else "both" if before and after
                        else "first_begins_before" if before else "last_ends_after" if after else "other")
            detail = {"case_id": row.case_id, "slot": slot, "gold": gold, "current_decoded": current,
                "category": category, "any_exact_interval": interval, "whitespace_diagnostic": diagnostic,
                "target_first_start": first, "target_last_end": last, "target_boundary": boundary}
            details[row.case_id][slot] = detail
            values = stats[slot]
            values["denominator"] += 1
            values["categories"][category] += 1
            if diagnostic != "exact":
                values["whitespace_mismatches"][diagnostic] += 1
            for key, yes in [("first_token_start_exact", first_exact), ("last_token_end_exact", last_exact),
                             ("both_boundaries_exact", first_exact and last_exact)]:
                values["boundary_alignment"][key] += int(yes)
            values["target_boundaries"][boundary] += 1
            examples = values["examples"].setdefault(boundary, [])
            if len(examples) < 5:
                examples.append(detail)
    for values in stats.values():
        n = values["denominator"]
        a, b, c = (values["categories"][key] for key in "ABC")
        require(a + b + c == n, "category_partition")
        values.update(current_label_roundtrip_exact=a, current_label_roundtrip_not_exact=b+c,
            current_label_roundtrip_rate=a/n, any_token_exact_representable=a+b,
            any_token_exact_nonrepresentable=c, any_token_exact_rate=(a+b)/n,
            category_rates={key: value/n for key, value in values["categories"].items()})
        require(sum(values["whitespace_mismatches"].values()) == b+c, "mismatch_partition")
    return {"slots": stats, "supported_unknown_o_only_rows": unknown_checked,
            "blocked_unrendered_null_target_rows": blocked}, details


def read_prior() -> dict[str, Any]:
    result = json.loads(RESULT79.read_bytes())
    unsigned = dict(result)
    digest = unsigned.pop("canonical_result_sha256")
    require(digest == RESULT79_HASH and canonical_hash(unsigned) == digest, "prior_result_identity")
    require(result["identities_before"]["model_aggregate_sha256"] == REVIEWED_AGGREGATE, "reviewed_artifact_identity")
    return result


def cross_reference(prior: dict[str, Any], rows: list[Any], details: dict[str, Any]) -> list[dict[str, Any]]:
    plays = [p for p in prior["validation"]["predictions"] if p["intent"] == "play"]
    require(len(plays) == len({p["case_id"] for p in plays}) == 11, "prior_play_count")
    by_id = {r.case_id: r for r in rows}
    result = []
    for prediction in plays:
        row = by_id[prediction["case_id"]]
        require(row.ai_scope == "supported" and row.expected.intent == "spotify_play_track", "prior_play_scope")
        gold = raw_span(row.expected.track)
        predicted = prediction["track"]
        result.append({"case_id": row.case_id, "expected_track": gold, "recorded_predicted_track": predicted,
            "gold_category": details[row.case_id]["track"]["category"],
            "whitespace_diagnostic": whitespace_kind(row.utterance, predicted, gold),
            "start_delta": predicted["start"] - gold["start"], "end_delta": predicted["end"] - gold["end"]})
    return result


def decision(validation: dict[str, Any]) -> str:
    track = validation["slots"]["track"]
    require(track["denominator"] == 300, "track_gate_denominator")
    if track["any_token_exact_representable"] < 285:
        return TRACK_STOP
    return TARGET_STOP if track["current_label_roundtrip_exact"] < 285 else PASS


def run_audit() -> dict[str, Any]:
    require(Path(sys.executable).resolve() == PYTHON.resolve() and sys.flags.utf8_mode == 1, "qualified_utf8_python_required")
    require(os.environ.get("HF_HUB_OFFLINE") == os.environ.get("TRANSFORMERS_OFFLINE") == "1", "offline_required")
    require(all(os.environ.get(key, "false").casefold() == "false" for key in FLAGS), "authority_flag_changed")
    opened: set[str] = set()
    denied: list[str] = []
    sys.addaudithook(read_guard(opened, denied))
    identity = tokenizer_identity()
    prior = read_prior()
    tokenizer = load_tokenizer()
    config = json.loads((ARTIFACT / "rl_agent_config.json").read_bytes())
    result = {"schema": "laya-span-representability-v1", "repo_base": BASE, "tokenizer_identity": identity,
        "authority_flags": dict(FLAGS), "splits": {}, "inputs": {},
        "prior_result_sha256": RESULT79_HASH, "pr79_rescored": False}
    for name in SPLITS:
        raw = split_path(name).read_bytes()
        rows = parse_split(name, raw)
        report, details = audit_split(rows, tokenizer, config)
        result["inputs"][name] = {"sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows), "supported_play": SPLITS[name][1]}
        result["splits"][name] = report
        if name == "validation":
            result["pr79_play_cross_reference"] = cross_reference(prior, rows, details)
        require(split_path(name).read_bytes() == raw, "frozen_split_mutated")
    require(tokenizer_identity() == identity, "tokenizer_mutated")
    result["status"] = decision(result["splits"]["validation"])
    result["optional_slot_remaining_blockers"] = [slot for slot in ("artist", "album")
        if result["splits"]["validation"]["slots"][slot]["any_token_exact_rate"] < .95]
    result["process_boundary"] = {"utf8_mode": sys.flags.utf8_mode, "offline": True,
        "torch_imported_incidentally": "torch" in sys.modules, "tokenizer_only": True,
        "model_weights_opened": False, "protected_open_attempts": len(denied),
        "opened_corpus_splits": sorted(opened), "held_out_rows_opened": False, "stage_a_rows_opened": False,
        "model_compute_calls": 0, "trained_artifact_accessed": False}
    result["source_sha256"] = {name: hashlib.sha256((ROOT / "scripts" / name).read_bytes()).hexdigest()
        for name in ("local_ai_stage_b_laya_adapter.py", "local_ai_stage_b_laya_small_adaptation.py")}
    result["canonical_result_sha256"] = canonical_hash(result)
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(run_audit(), sort_keys=True, ensure_ascii=True, indent=2))
    except (ValueError, PermissionError) as error:
        print(json.dumps({"status": "LAYA_SPAN_REPRESENTABILITY_AUDIT_BLOCKED", "blocker": str(error)}))
        raise SystemExit(1)
