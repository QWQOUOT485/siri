# Agent Rules

Behavior rules for coding agents working on this project.

## Before Coding
1. Read docs/SECURITY.md — highest priority
2. Read docs/SPEC.md for product requirements
3. Read docs/ARCHITECTURE.md for system design
4. If modifying Windows Adapters → read docs/WINDOWS.md
5. If modifying Parser → read docs/SPEC.md
6. If modifying API → read docs/API.md + docs/SECURITY.md
7. If modifying networking → read docs/NETWORKING.md
8. If modifying Spotify/music playback → read docs/SPOTIFY.md + docs/SECURITY.md
9. After completing work → run relevant tests per docs/TESTING.md

## Document Priority
```
SECURITY.md
    ↓
SPEC.md
    ↓
ARCHITECTURE.md
    ↓
WINDOWS / NETWORKING / API
    ↓
TASKS.md
```
TASKS cannot override security or product specifications.

## Absolute Rules
- NEVER allow user input to reach shell/subprocess directly
- NEVER provide remote shell / remote execution capability
- NEVER delete security tests to make CI pass
- NEVER commit secrets (.env, API keys)
- NEVER add public network access
- NEVER add LLM integration (v1)
- NEVER add Remote Shell
- Windows native API preferred over third-party packages
- Evaluate OSS before use: maintenance status, security, license
- Don't over-engineer

## When Using External Libraries
- Check GitHub for mature OSS solutions first
- Verify: maintained, secure, clear license, good Windows support
- If only 10 lines of Windows API needed, don't import a huge framework
- Can reference: Microsoft docs, Python docs, FastAPI docs, Windows API docs, Apple Shortcuts docs

## Source of Truth
- Original specification: docs/SOURCE_SPEC.md (read-only reference, don't modify)
- If you find a conflict between docs, SOURCE_SPEC.md is the final arbiter
