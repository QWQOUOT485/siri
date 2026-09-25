# MiniMind training-method reference for Local AI research

**Status: research reference only; not executed.**

This document records how [jingyaogong/minimind](https://github.com/jingyaogong/minimind)
may be used as a training-method reference for future Local AI / Jev-style
adaptation work.

Pinned reference reviewed for this note:

- repository: `jingyaogong/minimind`
- commit: `f659b55761b754d306bd140573493a6543cafd7f`
- license: Apache-2.0
- current mainline model family reviewed: MiniMind-3, including the small dense
  model and MoE variant described by the upstream project

This is **not** a ninth Stage A candidate, a Stage B finalist decision, a
training authorization, a model recommendation, a production dependency, or an
executable-fallback change.

The project authority boundary remains unchanged:

```text
training_authorized=false
model_compute_authorized=false
LOCAL_AI_FALLBACK_APPROVED=false

model output
→ RawAIIntent / bounded typed proposal
→ deterministic grounding
→ policy
→ ValidatedAction
→ trusted adapter
```

MiniMind examples must never be used to bypass grounding, policy,
clarification-token ownership, trusted Spotify ID resolution, or the closed
ValidatedAction boundary.

## Why keep MiniMind as a reference

MiniMind is useful here because it exposes a relatively small, readable,
PyTorch-first implementation of several training stages that would otherwise
be hidden behind large framework abstractions.

The useful part for this Agent is the **training machinery and experiment
design**, not replacing the current candidate set with the MiniMind-3 model.

Relevant upstream areas include:

- full SFT training loop
- LoRA / small-model adaptation examples
- checkpoint and resume handling
- model distillation
- GRPO / CISPO / PPO research paths
- Agentic RL with multi-turn tool-use trajectories
- rollout-engine separation

These are implementation references only. Candidate-specific architecture and
training objectives remain authoritative for Stage B.

## Recommended reuse boundary

### 1. SFT / adaptation loop — useful reference

MiniMind's simple SFT path is a useful example for:

- mixed precision
- optimizer / scheduler wiring
- gradient clipping
- checkpoint save/resume
- deterministic seeding
- compact experiment logging

Do **not** force every Stage B candidate into a causal-LM SFT objective.

- decoder candidates may use LoRA / QLoRA / supervised typed-output training
  when appropriate;
- encoder candidates such as Laya should keep their intended
  classification/decision-head training route;
- Decider-style typed projection should keep its native decision objective when
  that is the architecture being tested.

The benchmark must compare the intended model method, not whichever method is
easiest to copy from MiniMind.

### 2. Distillation — high-value future experiment

A future Stage B research path may test teacher-to-student distillation:

```text
stronger local teacher
→ sanitized Siri decision examples
→ deterministic / reviewed filtering
→ candidate-native student adaptation
→ validation set
→ sealed held-out evaluation
```

Possible teacher output includes only bounded semantic targets such as:

- `spotify_play_track` vs `unknown`
- track / artist / album semantic spans
- bounded entity-boundary recovery
- optional calibrated soft targets where the student architecture supports them

Teacher output is **untrusted training evidence**. It does not become authority
and must not contain or create:

- shell / PowerShell / CMD content
- executable paths
- arbitrary URLs
- client-owned Spotify IDs / URIs
- clarification tokens
- secrets or private runtime paths

The sealed held-out labels must never be exposed to the teacher, prompt-tuning
loop, data filtering logic, or training process. Distillation data must remain
strictly separated from the held-out seal.

This path is especially interesting if a stronger Qwen-class teacher can
transfer narrow Traditional-Chinese / mixed-language Siri semantic behavior
into a much smaller typed decision model.

It is only a future experiment until the existing Stage B authorization gates
explicitly permit model compute and training.

### 3. Agentic RL — later research only

MiniMind's Agentic RL path is relevant to a future bounded planner or
multi-step semantic decision model, but its tool-use examples must be adapted
to this project's stricter authority model.

Do not train:

```text
LLM
→ arbitrary tool call
→ execution
```

If Agentic RL is ever evaluated here, the trajectory must preserve:

```text
model proposes bounded intent / plan
→ deterministic grounding
→ policy
→ closed ValidatedAction
→ trusted capability
```

Reward design must therefore reward safe semantic decisions and correct
clarification/unknown behavior, not direct provider IDs or unrestricted tool
execution.

Agentic RL is not required for the current narrow Stage B decision-model study
and should not be introduced before simpler supervised / decision-head /
distillation methods are measured.

## What not to copy

### From-scratch pretraining

Training a general MiniMind-style base model from scratch is not a current
project goal. The Siri task is narrow enough that adapting an existing released
backbone or decision model is the more relevant research path.

### MiniMind generic benchmarks

C-Eval, C-MMLU and other generic LLM benchmarks do not replace this project's
Agent benchmark.

The project-owned Stage B metrics remain authoritative for this research,
including:

- supported semantic accuracy
- safe-unknown behavior
- false execution / false acceptance
- slot and entity-boundary accuracy
- Traditional-Chinese / English / mixed-language slices
- calibration
- latency and memory use
- fail-closed behavior

### Direct tool authority

MiniMind tool-calling examples are not permission to let a model select trusted
Spotify IDs, execute Windows actions, own clarification tokens, or bypass the
policy gate.

### Long-term memory

MiniMind is a model-training reference, not a Personal Memory implementation.
The existing high-trust Semantic Memory and future bounded low-trust
`MemoryProvider` research remain separate.

## RX 9070 XT constraints

All future project-owned Stage B experiments remain subject to the existing
RX 9070 XT hardware protocol.

The current hardware evidence proves only a small PyTorch/ROCm tensor operation.
It does **not** authorize:

- model loading
- forward/backward
- optimizer steps
- training
- candidate qualification
- latency acceptance

Do not run MiniMind-derived training merely because the basic tensor preflight
passed.

If a future authorized experiment borrows MiniMind code, first qualify the
exact model, dtype, operator set, forward/backward path, optimizer path, and
checkpoint behavior on the project's RX 9070 XT environment.

## Suggested future experiment order

Only after the existing authorization gates are explicitly opened:

1. candidate-native supervised adaptation baseline;
2. LoRA / small decision-head tuning where appropriate;
3. teacher→student distillation on sanitized non-held-out data;
4. compare against the same sealed held-out benchmark;
5. only then consider RL / Agentic RL if supervised methods leave a measured
   gap that RL is suited to address.

At every step:

```text
better benchmark result
≠ production approval
≠ executable authority
```

Production promotion still requires the separate grounding, policy,
fail-closed, production-aligned shadow, real Windows/Spotify/Siri acceptance,
and independent review gates.
