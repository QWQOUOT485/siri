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
- Studio/original wins against Live when no version was requested
- Explicit Live intent wins against studio/original
- Multiple Live versions remain ambiguous
- Bare same-title tracks by different artists remain ambiguous
- Same-ISRC release duplicates may collapse safely
- Duration alone never resolves two candidates
- Ambiguous Spotify search results do not auto-play an arbitrary track
- Spotify API calls are mocked in unit tests
- Spotify access/refresh tokens are never returned or logged
- User song/artist/album strings never become executable paths, shell commands, command-line arguments, process IDs, or arbitrary URLs
- Pause / next / previous map to Spotify playback actions
- Lock parsing
- Malicious command rejection
- Arbitrary executable path rejection
- Arbitrary URL rejection
- Shell command rejection
- PowerShell injection rejection
- CMD injection rejection

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
