# Testing Specification

All security-related test requirements defined in the [Security Specification](SECURITY.md) are mandatory.

## Test Architecture
Tests are split into two categories that MUST be kept separate:
1. **Unit Tests** - mock Windows calls, can run in any environment
2. **Windows Integration Tests** - only run on real Windows, no destructive operations

## Unit Tests
All mock-based, can execute in any environment (including non-Windows CI):
- Command parser (Chinese and English)
- Application matching (exact, alias, Chinese alias, fuzzy, ambiguous, unknown)
- Application normalization
- Action schema validation
- Authentication (success, failure, missing)
- Shutdown service (request, confirmation, expired token, reused token, invalid token)
- API endpoint testing
- Process resolver (mocked)
- Adapters (mocked)
- Volume limit validation
- Website allowlist
- Spotify media parser
- Bare `play` / 「播放」 maps to `spotify_resume`
- `播放晴天` parses a track title
- `播放周杰倫的晴天` parses track + artist
- `播放周杰倫的晴天 (葉惠美)` parses track + artist + album/version hint
- `播放周杰倫的晴天，專輯葉惠美` parses a natural album hint
- `播放葉惠美專輯的晴天` parses a leading album hint
- `播放晴天現場版` / `播放晴天原版` parses a closed version hint
- Spotify search ranking prefers exact title + artist matches
- Live/Concert/Tour/演唱會/現場候選在一般搜尋中直接排除
- Explicit Live intent is rejected before Spotify search/playback
- Traditional/Simplified normalization only collapses same-ISRC identity duplicates
- Bare same-title tracks by different artists remain ambiguous
- Same-ISRC release duplicates may collapse safely
- Duration alone never resolves two candidates
- Ambiguous Spotify search results do not auto-play an arbitrary track
- Ambiguous results expose at most three trusted candidates and a short-lived server-owned clarification context; explicit selection is one-use and every successful recovery page rotates the token
- Clarification context invalidates after three unclear attempts, and concurrent selection/attempt updates are atomic
- Candidate recovery keeps an internal pool bounded, exposes at most three public options, filters Live/Concert results, suppresses already-shown provider IDs, shares a two-round user-visible budget across local/provider pages, and never auto-plays a recovered result
- Reviewed exact recovery phrases (`都不是`, `不是這些`, `換一批`, `再一批`, `none of these`, `not these`, `another batch`, `next batch`, `different ones`) use only the server-owned clarification token; unreviewed prefixes plus client-supplied track IDs, URIs, offsets, and recovery cursors are rejected
- Candidate recovery exhaustion is fail-closed; the Sad overlxrd first-occurrence path requires explicit selection and successful playback before alias learning
- Spotify API calls are mocked in unit tests
- Spotify 429 with bounded `reason` parsing (`QUOTA_EXCEEDED`), capped/malformed `Retry-After`, no token leakage, and no transport call during fake-clock cooldown
- Explicit `QUOTA_EXCEEDED` may block all Web API scopes, while ordinary Search, personalization, and playback 429s remain operation-scoped
- Web API cooldown does not block OAuth token refresh after a 401 recovery path
- Top Tracks / Top Artists / Recently Played personalization cache hits, TTL expiry, stale-on-refresh-error fallback, account-context isolation, and bounded eviction
- Shared `SpotifyCatalog` + clarification store + `SpotifyPlayer` composition proves ordinary personalization 429 does not block the selected track's playback request
- Spotify access/refresh tokens are never returned or logged
- User song/artist/album strings never become executable paths, shell commands, command-line arguments, process IDs, or arbitrary URLs
- Pause / next / previous map to Spotify playback actions
- Chinese skip commands accept only `下一首歌` / `上一首歌`; the shorter `下一首` / `下一曲` / `上一首` / `上一曲` forms are rejected to avoid Siri misrecognition
- Next / previous resume the selected track after skipping, including when the configured device was inactive or paused
- Next with no Spotify next item returns `SPOTIFY_NO_NEXT_TRACK` and does not restart the current track
- Next only resumes after the playback track identity changes; an already-playing new track is not restarted
- Lock parsing
- Malicious command rejection
- Arbitrary executable path rejection
- Arbitrary URL rejection
- Shell command rejection
- PowerShell injection rejection
- CMD injection rejection
- Local AI strict schema rejects extra authority fields and requires schema version 1
- Local AI grounding rejects partial/ungrounded track spans and drops ungrounded optional slots
- Local AI eligibility rejects clarification tokens, hostile input, and non-Spotify domains
- Local AI loopback adapter enforces bounded transport and shadow mode never returns an executable action
- Local AI promotion matrix covers malformed output, connection/timeout, busy, oversized response, ungrounded track, invented optional slots, and policy rejection without creating an action; this is source/unit evidence and must not be reported as live transport acceptance

Unit tests MUST mock Windows system calls. Tests must NOT actually: shutdown, lock, close Chrome, open Photoshop, adjust volume, or kill processes.

## Security Tests
These are a subset of unit tests focused on security. See [Security Specification: Security Test Requirements](SECURITY.md#security-test-requirements).
Security tests MUST NOT be deleted to make CI pass.

## Windows Integration Tests
Only executed on real Windows environments:
- Application discovery (built-in apps found)
- Start Menu .lnk shortcut parsing
- Registry App Paths discovery
- AppsFolder / AUMID discovery
- Catalog refresh
- Interactive session detection
- Network profile detection
- Safe test fixture launch (if available)

Integration Tests MUST NOT actually:
- shutdown
- lock
- force kill user applications

## Test Framework
`pytest` or an equivalent reasonable Python test framework must be used.

## Test Directory Structure
- `tests/unit/` — all mock-based tests
- `tests/integration_windows/` — real Windows only tests

## Important Notes
- Specific `pytest` commands and final operational steps are determined during implementation, not pre-specified in this spec.
- Security tests MUST NOT be deleted to make CI pass (as per AGENTS.md rules and SECURITY.md).
- Unit and Windows Integration tests must be clearly separated in the directory structure and CI/verification flow.


## Exact Volume / Spotify Playback-State Tests

Required unit/security coverage for the approved deterministic-controls batch:

### Windows exact master volume

- Chinese/English exact-percent parser cases
- accept 0 and 100
- reject values outside 0–100
- `音量降低到 30%` parses as absolute `set_volume(30)`, not relative volume-down
- action schema rejects `volume_percent` on unrelated actions
- pycaw scalar conversion for 0/37/100
- exact setter failure does not fall back to approximate media keys
- exact scalar operation does not silently toggle mute
- existing relative up/down fallback behavior remains intact

### Spotify shuffle

- on/off parser mappings
- fixed boolean state only
- 401/403/429 behavior
- no arbitrary endpoint/body control

### Spotify repeat

- track/context/off parser mappings
- reject free-form repeat modes
- preserve deterministic closed enum/state

### Spotify continue

- repeat-off operation occurs
- resume occurs
- existing shuffle state is preserved
- no queue/context is invented
- failures are surfaced rather than partially reported as success

### Volume-domain separation

- `音量 30%` → Windows `set_volume`
- `Spotify 音量 30%` → `spotify_set_volume`
- one domain never silently falls back to the other

### AI/security

- Local AI cannot emit these newly added deterministic controls in its initial schema/allowlist
- numeric fields cannot carry expressions, shell text, URLs, paths, or command chaining

Safe Windows/Spotify runtime acceptance is required before marking the features implemented. See [PLAYBACK_CONTROLS.md](PLAYBACK_CONTROLS.md).
