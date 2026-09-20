# Semantic Memory Phase 1 Runtime Acceptance — 2026-09-20

Status: **NO-GO for enablement**

This report records the Phase 1 runtime/rollout evidence for Local Semantic
Recovery. It keeps source/unit, current-source Windows, installed Windows,
Spotify, Siri, and performance evidence separate. No production semantic-memory
database, token, API key, or transcript was created or changed by this check.

## Decision

Keep `LOCAL_SEMANTIC_MEMORY_ENABLED=false` for the installed Agent. Do not
promote the feature until the installed runtime contains the current Phase 1
implementation and the real Spotify/Siri sequence is accepted.

## Evidence summary

| Gate | Result | Boundary |
| --- | --- | --- |
| Source/unit Semantic Memory tests | **PASS** — 43 passed | Current repository only |
| Full source suite | **PASS** — 246 passed, 2 deprecation warnings | Current repository only |
| Windows current-source lifecycle harness | **PASS** | Temporary DB, fake Windows adapters, no production config |
| Spotify clarification/memory integration | **PASS** — 25 targeted tests passed | HTTP-mocked Spotify only |
| Installed Windows Agent | **NOT READY** | Installed copy predates Semantic Memory |
| Real Spotify account | **NOT RUN** | No current installed Semantic Memory runtime |
| iPhone/Siri voice E2E | **NOT RUN** | No current installed Semantic Memory runtime |
| Production enablement | **NO-GO** | Required real-world gates remain open |

## Current-source Windows harness

The harness ran on Windows from the current repository virtual environment. It
used a temporary directory and injected fake Windows adapters and a mock
Spotify service. The harness did not touch the installed Agent or its token
file.

Observed results:

- Disabled startup: `enabled=false`, `available=false`, no SQLite file created.
- Controlled enabled startup: `available=true`, schema version `1`, foreign
  keys enabled, and the expected `entities`, `aliases`, `scope_context`, and
  `alias_observations` tables present.
- Trusted learning: a server-owned clarification/success fixture confirmed the
  `Sad overlxrd` alias to `SASIOVERLXRD`; the recovery result allowed exact
  canonicalization.
- Restart: closing and rebuilding the runtime reloaded the confirmed alias
  into the RAM index; exact recovery still returned `SASIOVERLXRD`.
- Fuzzy recovery returned candidate evidence only: no exact hit and no
  automatic canonicalization.
- A second trusted mapping for the same alias produced `conflicted`; recovery
  did not select either mapping.
- Eight concurrent confirmations for one entity produced one row with
  `confirmation_count=8`, with no conflicts or silent divergent RAM state.
- Corrupt and unavailable SQLite inputs disabled memory and returned an empty
  recovery path with `SEMANTIC_MEMORY_UNAVAILABLE`.

The same Windows harness measured 1,000 exact RAM lookups over the small
fixture: P50 `0.0174 ms`, P95 `0.0231 ms`, four confirmed aliases, and a
40,960-byte temporary SQLite file. This is not an installed-host benchmark;
RSS/RAM usage was not measured. The Phase 2 scale benchmark remains separate.

The configuration probe also confirmed that the default is disabled,
observations default to disabled, and setting
`LOCAL_SEMANTIC_MEMORY_FUZZY_AUTO_RETRY=true` cannot open the code-level fuzzy
automatic-retry gate.

## Spotify and regression evidence

The current-tree mocked integration passed the first-clarification → trusted
selection → successful playback → alias learning → second exact-hit sequence.
It also passed the playback-failure/no-learning case. The selected targeted
Spotify/parser/semantic-retry set passed 25 tests, and the complete source
suite passed 246 tests. This includes the source regression coverage for
`播放死亡是生命的終點` and the existing server-owned clarification boundary.

These are source and mocked-provider results. They do not prove a real Spotify
account, active device, real playback, or Siri voice behavior.

## Installed Windows Agent evidence — pre-alignment snapshot

The following is a historical snapshot taken before the installed-agent
alignment recorded in
[`SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md`](SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md).
It is not a statement of the current installed tree. At the time of this
check, the installed copy at `D:\ai\windows-siri-agent` was reachable through
its local health endpoint and read-only inspection found:

- pre-alignment check: no Semantic Memory modules were present in the installed
  `app` tree;
- pre-alignment check: installed `app\runtime.py` and
  `app\infrastructure\config.py` hashes differed from the repository versions
  that were current at that time;
- pre-alignment check: installed `.env` had no
  `LOCAL_SEMANTIC_MEMORY_*` keys;
- pre-alignment check: `runtime\semantic_memory` and its SQLite database were
  absent.

Therefore, at the time of this pre-alignment check, the installed Agent could
not execute the current Phase 1 runtime acceptance sequence. No installed
configuration or database was modified to force an artificial pass. The later
alignment is documented separately and confirms that the current `app` tree,
including `app\infrastructure\config.py`, now matches the reviewed source;
semantic memory remains disabled and no production SQLite artifact was
created.

## Open gates and smallest next action

1. **Completed after this snapshot:** stage/deploy the exact reviewed Phase 1
   source to an isolated Windows Agent runtime without copying secrets or
   enabling production memory. See
   [`SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md`](SEMANTIC_MEMORY_INSTALLED_ALIGNMENT_2026-09-20.md).
2. Run the first real Spotify clarification and successful playback for the
   `Sad overlxrd` case, then restart and verify the second exact hit.
3. Re-run the existing `播放死亡是生命的終點` regression and the established
   iPhone/Siri clarification flow.
4. Measure installed-host latency and RAM, then perform the independent rollout
   review. Only a clean result may change the disabled flag.

Until those gates pass, the current source is reviewable but the feature is not
accepted for production enablement.
