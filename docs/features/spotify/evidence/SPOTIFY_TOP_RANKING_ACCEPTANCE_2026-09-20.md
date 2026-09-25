# Spotify Top Tracks / Top Artists ranking — real-account acceptance

Date: 2026-09-20

Decision: **PARTIAL ACCEPTANCE** — Top Track reordering is accepted for this
real-account probe; a standalone Top Artist reordering case is not yet proven.

## Scope and method

- Source revision: `74304144d51ed174a3619a32e76e07a04d8e87e0`.
- The token was reauthorized through the current source flow and included
  `user-top-read`, `user-read-recently-played`, and `user-library-read`.
- The probe used the fixed 20 bare-title queries plus a bounded in-memory
  sample of 50 titles returned by the account's Top Tracks endpoint. Track
  titles from that sample were not written to the repository or this report.
- For each genuine ambiguity, the probe examined only the existing bounded
  server-owned candidate set (at most three candidates).
- An accepted case required the final first candidate to differ from the
  original Search-order first candidate, the final candidate to have a real
  Top Track/Artist signal, and every candidate to have no saved or Recently
  Played signal. This isolates the Top signal without letting a stronger
  signal explain the reorder.
- The probe performed no playback, Library write, or full Library enumeration.

## Observed result

| Measure | Result |
| --- | ---: |
| Genuine ambiguity cases | 34 |
| Raw candidate sets comparable to Search order | 34 |
| Saved memberships observed | 15 |
| Top Track candidate matches | 19 |
| Top Artist candidate matches | 19 |
| Recently Played candidate matches | 13 |
| Accepted Top reorders | 1 |
| Search/API errors | 0 |
| Library lookup errors | 0 |
| Library writes | false |
| Playback | false |

The accepted case was a `top_track` reorder: a candidate at original Search
position `1` became final position `0`, while the ambiguity remained. Saved and
Recently Played signals were absent for that candidate set. The report omits
the account's track and artist names by design.

Top Artist data was read successfully and matched 19 candidates in the bounded
sets, but this run did not produce a Top-Artist-only reorder that could be
attributed separately from the Top Track signal. Therefore this is not a
standalone acceptance claim for the Top Artist signal.

## Safety and decision

The real case preserved genuine ambiguity and did not execute playback. The
existing source/unit suite also passed (`246 passed`, two dependency warnings),
including explicit-metadata precedence and ambiguity-safety regressions.

Keep the Top Tracks / Top Artists slice in **partial acceptance** status:

- Top Track real-account candidate reordering: accepted for the observed case.
- Top Artist standalone real-account reordering: not yet proven.
- Automatic playback, client-provided ranking authority, and Library writes:
  not enabled by this evidence.

The smallest next evidence-producing action is a bounded real-account query
that yields a Top-Artist-only reorder, or an explicit product decision to
accept the combined Top signal based on the Top Track case and proceed to the
Recently Played gate.

