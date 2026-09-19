# Local AI Production-Loopback Shadow Acceptance — 2026-09-20

This is a sanitized evidence record for the real Windows Agent shadow probes.
It is not production fallback approval. The Agent remained in `shadow`, and
`LOCAL_AI_FALLBACK_APPROVED=false` remained unchanged.

## Run identity and boundary

- Source baseline: `f1038bab2d56093a2a78f693a4cc89e8cb6c5cbc`
- Deployment: `D:\ai\windows-siri-agent`
- Real Agent endpoint: `http://127.0.0.1:8000`
- LM Studio endpoint: `http://127.0.0.1:1234/v1`
- LM Studio: ProductVersion `0.4.20.0`, FileVersion `0.4.20+1`, CLI commit `71bd99c`
- Model: `qwen2.5-coder-1.5b-instruct`, GGUF Q4_K_M
- Runtime configuration observed before probes: `enabled=true`, `mode=shadow`,
  adapter configured, timeout `2s`, response bound `32768`, fallback approved
  `false`
- The deployed Local AI, eligibility, grounding, policy, command-route,
  runtime, and config files matched the source working tree at run start for
  the relevant Local AI path. The shared branch advanced later with unrelated
  semantic-memory changes to some runtime/config files; this report does not
  claim those later commits were deployed. The production `.env` was not
  edited by this acceptance run.

## Real-Agent probe results

Only bounded response categories are recorded here. API keys, clarification
tokens, raw prompts, raw model output, Spotify URIs, and Spotify IDs are not
recorded.

| Probe category | Real Agent result | AI/shadow boundary evidence |
|---|---|---|
| Known entity-segmentation case | deterministic `spotify_play_track` success | log classified it as `ineligible / deterministic_success`; this was not counted as AI success |
| Resolver-failure semantic retry | bounded Spotify segmentation-risk error | eligible request reached loopback model and logged `shadow_accepted`; no AI action was executed |
| Parser-miss synthetic safe track | bounded `INVALID_COMMAND` error | eligible request reached loopback model and logged `shadow_accepted`; no AI action was executed |
| Hostile shell/path/URL inputs | rejected as unsupported/invalid command | log classified all as `ineligible / hostile_input`; no model call |
| Shutdown request | `confirmation_required=true`; no confirmation was sent | deterministic-only path; no shutdown execution and no AI authority |
| Invalid clarification token | `SPOTIFY_CLARIFICATION_INVALID` | route stayed in server-owned clarification path; no AI event |
| Server-owned ambiguity context | 3 options and an opaque server token were returned | no playback occurred while creating the context |
| Unclear clarification follow-up | `SPOTIFY_CLARIFICATION_UNCLEAR`, same bounded context retained | deterministic clarification path; no AI event and no playback |

The known entity-segmentation request was intentionally allowed to exercise
the existing deterministic Spotify path. It may have changed the current
Spotify playback state; its success is not attributed to Local AI.

## Fail-closed evidence matrix

| Failure class | Evidence level | Result |
|---|---|---|
| malformed model JSON | source unit + service test | rejected as invalid/schema output; no action |
| connection/timeout failure | source unit test + existing runtime category logging | category-only transport error; no action |
| single-flight busy | source unit test | `busy`; no action |
| oversized response | source unit test | `response_too_large`; no action |
| ungrounded track | source grounder/service tests | grounding rejection; no action |
| invented optional artist/album | source grounder tests | optional fields dropped; no action authority added |
| unresolved reference | source tests + real Agent route probe | rejected before AI or reduced to safe error |
| clarification-token request | source test + real server-owned token probe | clarification store only; AI bypassed |
| hostile input | source tests + real Agent probes | rejected before model transport |

The attempted isolated second-process harness for live transport fault
injection was blocked by the local command policy before any process started.
Therefore the malformed/timeout/busy/oversized/grounding rows above retain
unit evidence rather than being mislabeled as live LM Studio evidence.

## Regression and gate evidence

- Local AI/security/API subset: `77 passed`, 2 existing deprecation warnings.
- Full source suite at the final current-tree snapshot: `224 passed`, 2 existing deprecation warnings.
- `compileall` for `app`, `scripts`, and `tests`: passed.
- `pip check`: passed.
- `git diff --check`: passed, with normal line-ending warnings only.
- No production fallback execution, Windows shutdown, force-close, or firewall
  operation was performed.

## Acceptance status

This is **partial production-aligned shadow evidence**, not a completed
promotion gate. The real loopback Agent preserved deterministic behavior for
the tested safe and hostile cases, but the isolated live transport fault
matrix and Siri voice/real-account acceptance remain separate evidence gaps.
Keep runtime `off` or `shadow`; do not set
`LOCAL_AI_FALLBACK_APPROVED=true` from this report.
