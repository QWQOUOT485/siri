# Spotify Recently Played ranking — real-account acceptance

Date: 2026-09-20  
Source revision: `d542774` (merged Top ranking acceptance baseline)  
Probe: `scripts/spotify_recent_ranking_acceptance.py`

## Decision

**BLOCKED — Recently Played real-account acceptance is not proven.**

The probe's candidate/membership boundary check was corrected to compare the
server-owned URI set rather than its pre-personalization order. The bounded
probe then completed against the live Spotify read path with the reauthorized
local token, but no candidate met all recent-only reorder criteria. This is
not evidence that the source slice is broken; it means the real account did
not provide an isolating case in this bounded run.

## Scope and safety boundary

- The probe uses the fixed 20 bare-title queries and, when requested, at most
  50 Recently Played track titles held in memory only.
- It reads only Search, Library membership, Top Tracks, Top Artists, and
  Recently Played data through fixed adapter methods.
- It does not enumerate the Library, start playback, or call a Library write
  endpoint.
- Account track and artist names are not emitted or stored in this report.

## Evidence

- The system Python did not contain the project dependency `pydantic`; the
  source checkout virtual environment was then used successfully.
- The virtual-environment run reached the live probe with all required scopes.
- The probe now binds each ambiguity case to the membership result created by
  that same Search call and compares candidate membership as an unordered
  server-owned URI set, because personalization may reorder the final tuple.
- The completed run observed 20 genuine ambiguities and 20 comparable raw
  candidate sets. Recently Played matched 6 candidates; saved matched 1,
  Top Track matched 1, and Top Artist matched 7.
- Search, Library, Top, and Recently Played errors were all 0.
- No acceptance case, playback, or Library write was observed.
- `python -m py_compile scripts/spotify_recent_ranking_acceptance.py` passed.

## Unknown and smallest next action

The bounded account data did not contain a case where Recently Played alone
changed the first candidate while saved and Top signals were absent. Do not
treat the current run as acceptance; a future run needs either a new
bounded corpus or an explicit product decision to accept the source slice
without a recent-only real-account reorder.
