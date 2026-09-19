# Spotify saved/liked ranking — real-account acceptance

Date: 2026-09-20

Decision: **ACCEPTED — bounded real-account ordering case obtained**

This report records the current-source read-only probe for the saved/liked
candidate-ordering slice. The acceptance is for the bounded case below; it is
not a claim that every future Search corpus will contain a saved reorder. It
does not replace the deterministic safety rules in `docs/SECURITY.md` and
`docs/SPOTIFY.md`.

## Scope and method

- Source baseline: `c0611bf` (PR #19 merge); the probe hardening and bounded
  corpus extension are included in this change.
- The probe used the existing local Spotify token store from the installed
  Agent. The access token value was not printed or committed.
- The token was unexpired for the run and included `user-library-read` and
  `user-read-recently-played`.
- The probe used the fixed 20 bare-title queries plus at most 50 Recently
  Played track titles as a bounded, in-memory search corpus. The Recently
  Played data was used only to seed search text; the saved probe's ranking
  client exposed only Search and Library membership, so the acceptance case
  isolated the saved signal.
- For each existing genuine ambiguity, it queried membership only for the
  bounded, server-owned candidate set (at most three tracks) through
  `GET /me/library/contains`.
- It did not enumerate the user's Library, play a track, or call any Library
  write endpoint.
- Account track and artist names stayed in memory and were not emitted in the
  result.

## Observed result

The probe returned:

| Measure | Result |
| --- | ---: |
| Bounded Recently Played title seeds | 50 |
| Genuine ambiguity cases | 20 |
| Saved memberships among checked candidates | 1 |
| Saved-only reorder cases | 1 |
| Accepted original → final position | 1 → 0 |
| Library lookup errors | 0 |
| Search/API errors | 0 |
| Library writes | false |
| Playback | false |

The accepted case preserved genuine ambiguity while a saved candidate moved
from original Search position 1 to final candidate position 0. The probe did
not auto-play it. This is the required real-account acceptance shape:

```text
raw Spotify Search order differs from the desired candidate order
→ one bounded trusted candidate is saved=true
→ saved signal reorders candidates
→ ambiguity remains and no automatic playback occurs
```

The read-only boundary behaved as intended, including the server-owned URI-set
membership check and the no-account-name output boundary.

## Gate decision and next action

The saved/liked slice has **bounded real-account acceptance**. Keep the
implementation on its existing deterministic fail-safe path: the saved signal
only reorders an existing trusted ambiguity set and never enables automatic
playback or removes ambiguity.

The next evidence-producing actions are the Top-Artist-only acceptance probe
and the separate Recently Played real-account acceptance probe. Neither should
enumerate the user's Library or manufacture a case with Library writes.

