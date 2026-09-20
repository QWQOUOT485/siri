# Spotify Top Tracks / Top Artists ranking — real-account acceptance

Date: 2026-09-20

Decision: **PARTIAL ACCEPTANCE** — Top Track reordering is accepted for this
real-account probe; a standalone Top Artist reordering case is not yet proven.
The follow-up Top-Artist-only probe is currently blocked by the provider's
Development Mode quota, not accepted as a pass.

## Scope and method

- Initial Top Track evidence source revision:
  `74304144d51ed174a3619a32e76e07a04d8e87e0`.
- The follow-up probe implementation is based on merged revision `9d92374`.
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

## Top-Artist-only follow-up

The follow-up probe added a bounded, read-only Top Artist corpus path. It can
use at most 50 Top Artists and at most 50 in-memory seed titles, and its
`--top-artist-only` mode accepts a case only when the final first candidate is
newly promoted by Top Artist with no saved, Top Track, or Recently Played signal.
No seed title or account name is written to the repository or report.

A diagnostic partial run found 8 Top-Artist-only opportunities, but all 8 had
the Top Artist candidate already first in the raw Search order, so there were
0 Top-Artist-only reorders. That run also encountered 25 Search HTTP 429
responses and therefore is not acceptance evidence.

A smaller bounded rerun was stopped at corpus seeding by Spotify:

| Measure | Result |
| --- | ---: |
| Status | blocked |
| Blocked operation | Top Artist seed lookup |
| HTTP status | 429 |
| Provider reason | `QUOTA_EXCEEDED` |
| `Retry-After` | 3600 seconds |
| Probe retry used | false |
| Rate-limit exhausted | true |

The probe records only the bounded status, provider reason, and retry delay.
It does not retry a `QUOTA_EXCEEDED` response or busy-loop; no further Spotify
calls were made after this blocker appeared.

## Post-restart verification

After the workstation restart, the first probe from this repository reported a
missing local token because the active Agent token store is kept outside this
repository. The existing local refresh token was used through the source auth
manager; the access token refreshed successfully and no token value was
printed or logged. Re-running the same bounded probe then returned the same
`429 QUOTA_EXCEEDED` with `Retry-After: 3600`. This confirms that the current
blocker is the provider quota, not token expiry or a missing refresh token.

Per the project stop rule, no further Spotify calls will be made until the
provider quota window is known to have cleared.

## Safety and decision

The real case preserved genuine ambiguity and did not execute playback. The
existing source/unit suite also passed (`246 passed`, two dependency warnings),
including explicit-metadata precedence and ambiguity-safety regressions.

Keep the Top Tracks / Top Artists slice in **partial acceptance** status:

- Top Track real-account candidate reordering: accepted for the observed case.
- Top Artist standalone real-account reordering: not yet proven.
- Automatic playback, client-provided ranking authority, and Library writes:
  not enabled by this evidence.

The current smallest next evidence-producing action is one bounded,
read-only Top-Artist-only query after the provider quota window clears. Until
then, keep this slice in partial acceptance and do not claim standalone Top
Artist acceptance. An explicit product decision could instead accept the
combined Top signal based on the existing Top Track case and proceed to the
Recently Played gate.
