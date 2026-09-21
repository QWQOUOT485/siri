"""Benchmark-only model storage resolution.

Model weights are external benchmark inputs, not application configuration.
This module gives every Stage A adapter one common root while retaining an
explicit per-candidate override for reproducibility and migration work.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ROOT_ENV = "LOCAL_AI_BENCHMARK_MODEL_ROOT"
DEFAULT_MODEL_ROOT = REPO_ROOT / "runtime" / "ai_poc" / "stage-a-models"

# These names are a storage layout only.  They are deliberately independent
# of model IDs and never become production configuration values.
CANDIDATE_MODEL_SUBDIRS: dict[str, str] = {
    "systemone-lite": "systemone-lite",
    "laya": "laya",
    "kev": "kev",
    "kev-base": "kev-base",
    "eve-rlcd": "eve-rlcd",
    "Verdict-open-jev": "Verdict-open-jev",
    "decider": "decider",
    "open-jev-deberta-v3-large": "open-jev-deberta-v3-large",
}


def resolve_model_root(
    model_root: Path | str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the common benchmark root without creating or modifying it.

    CLI input has precedence over ``LOCAL_AI_BENCHMARK_MODEL_ROOT``.  The
    repository-local ignored directory is the portable fallback used by
    tests and by callers that do not have an external model store.
    """

    if model_root is not None:
        return Path(model_root).expanduser()
    values = os.environ if environ is None else environ
    configured = values.get(MODEL_ROOT_ENV)
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_MODEL_ROOT


def resolve_candidate_model_dir(
    candidate_name: str,
    *,
    model_root: Path | str | None = None,
    override: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve a candidate's model directory; an explicit override wins."""

    if override is not None:
        return Path(override).expanduser()
    try:
        subdir = CANDIDATE_MODEL_SUBDIRS[candidate_name]
    except KeyError as exc:
        raise ValueError(f"unsupported benchmark model directory: {candidate_name}") from exc
    return resolve_model_root(model_root, environ=environ) / subdir


def candidate_model_subdir(candidate_name: str) -> str:
    """Return the fixed relative storage name for a known candidate."""

    try:
        return CANDIDATE_MODEL_SUBDIRS[candidate_name]
    except KeyError as exc:
        raise ValueError(f"unsupported benchmark model directory: {candidate_name}") from exc
