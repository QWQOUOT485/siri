# Spotify saved/liked ranking — real-account acceptance

Date: 2026-09-20

Decision: **NO-GO / not accepted**

This report records the current-source read-only probe for the saved/liked
candidate-ordering slice. It does not authorize production enablement and does
not replace the deterministic safety rules in `docs/SECURITY.md` and
`docs/SPOTIFY.md`.

## Scope and method

- Source revision: `c8f916cf07cfc8c2fb97a81b2c773c56e73229a0`.
- The probe used the existing local Spotify token store from the installed
  Agent. The access token value was not printed or committed.
- The token was unexpired for the run and included `user-library-read`.
- The probe used the script's fixed 20 bare-title queries.
- For each existing genuine ambiguity, it queried membership only for the
  bounded, server-owned candidate set (at most three tracks) through
  `GET /me/library/contains`.
- It did not enumerate the user's Library, play a track, or call any Library
  write endpoint.

## Observed result

The probe returned:

| Measure | Result |
| --- | ---: |
| Genuine ambiguity cases | 15 |
| Saved memberships among checked candidates | 0 |
| Library lookup errors | 0 |
| Search/API errors | 0 |
| Library writes | false |
| Playback | false |

No case showed a saved candidate moving ahead of the original Spotify Search
order. Therefore the required real-account acceptance case was not obtained:

```text
raw Spotify Search order differs from the desired candidate order
→ one bounded trusted candidate is saved=true
→ saved signal reorders candidates
→ ambiguity remains and no automatic playback occurs
```

The read-only boundary behaved as intended, but the absence of a saved
candidate in this query set is not evidence that the ordering slice is
accepted.

## Gate decision and next action

Keep the saved/liked slice **not accepted** and keep the implementation on its
existing deterministic fail-safe path. Do not claim real-account ordering
acceptance from this run.

The smallest next evidence-producing action is a user-approved known saved
track title that also has a competing trusted same-title candidate in bare
Spotify Search results; run the existing `--title` probe for that title. Do
not enumerate the user's Library to manufacture a case. Until such a case is
available, keep this item under `Not Yet Proven` in `PROJECT_STATUS.md`.

