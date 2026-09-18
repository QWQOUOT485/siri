# Current Tasks

## Current Milestone
Complete Windows Siri Agent v1.

## Before Coding
1. Read AGENTS.md
2. Read docs/SECURITY.md
3. Read relevant docs/SPEC.md sections
4. Read docs/ARCHITECTURE.md
5. If touching Windows adapters → read docs/WINDOWS.md
6. If touching API → read docs/API.md
7. Before finishing → read docs/TESTING.md

## Recommended Implementation Order
1. Project skeleton + directory structure
2. Configuration (config loading, .env)
3. Authentication (API key generation, validation, constant-time compare)
4. Action schema (closed action enum + ValidatedAction model)
5. App models (AppEntry, LaunchSpec, ProcessSpec, stable app_id)
6. Application discovery (Trusted Launch Sources + Metadata-only Sources)
7. Application catalog (in-memory, cache, refresh)
8. Matcher (normalize, alias, fuzzy, confidence, ambiguous handling)
9. Windows adapters (launcher, process, media, volume, system, firewall)
10. Command parser (Chinese + English, rule-based, no LLM)
11. Spotify integration (PKCE auth, token refresh, catalog search, device selection, named-track playback)
12. API routes (/health, /info, /apps, /action, /command)
13. Setup scripts (setup.ps1, start.bat, Task Scheduler, firewall, Spotify OAuth setup)
14. Siri integration documentation
15. Unit tests (all mocked, including Spotify API)
16. Windows integration tests (real Windows only, no destructive ops)
17. Final verification

## Definition of Done
- All security invariants from docs/SECURITY.md are implemented
- All API endpoints functional per docs/API.md
- Application discovery finds common Windows programs
- Chinese and English commands work
- Spotify named-track playback works with track + optional artist input
- Spotify OAuth tokens remain local and are never exposed to Siri/iPhone
- Shutdown requires two-step confirmation
- No user input reaches shell/subprocess
- Unit tests pass
- Windows integration tests pass on real Windows
- setup.ps1 creates working environment
- start.bat launches Agent
- README is user-friendly
