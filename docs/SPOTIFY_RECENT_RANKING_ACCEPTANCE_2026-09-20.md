# Spotify Recently Played ranking — real-account acceptance

Date: 2026-09-20  
Source revision: `d542774` (merged Top ranking acceptance baseline)  
Probe: `scripts/spotify_recent_ranking_acceptance.py`

## Decision

**BLOCKED — Recently Played real-account acceptance is not proven.**

The bounded probe reached the live Spotify read path with the reauthorized
local token and stopped at its defensive server-owned candidate/membership
boundary check. The run did not produce a qualifying reorder case. This is a
probe/runtime-shape blocker, not evidence that Recently Played ranking works
or fails.

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
- The virtual-environment runs reached the live probe and returned the
  sanitized `malformed_library_membership` boundary result.
- A stale-result indexing defect was fixed so each ambiguity case is matched
  to the membership result created by that same Search call; the same
  defensive boundary result remained.
- No acceptance case, playback, or Library write was observed.
- `python -m py_compile scripts/spotify_recent_ranking_acceptance.py` passed.

## Unknown and smallest next action

The exact shape/order of the live membership batch relative to the catalog's
current candidate tuple is not yet known. The smallest next evidence-producing
action is one sanitized, in-memory diagnostic of those lengths and URI-set
boundaries, followed by one controlled read-only rerun after the probe's
boundary assertion is corrected. Do not treat the current run as acceptance.
