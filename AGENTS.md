# Agent Rules

Behavior rules for coding agents working on this project.

## Before Coding
1. Read docs/SECURITY.md — highest priority
2. Read PROJECT_STATUS.md — current phase, completed work, and real-world acceptance status; this is a handoff summary, not a security/spec override
3. Read docs/SPEC.md for product requirements
4. Read docs/ARCHITECTURE.md for system design
5. If modifying Windows Adapters → read docs/WINDOWS.md
6. If modifying Parser → read docs/SPEC.md
7. If modifying API → read docs/API.md + docs/SECURITY.md
8. If modifying networking → read docs/NETWORKING.md
9. If modifying Spotify/music playback → read docs/SPOTIFY.md + docs/SECURITY.md
10. After completing work → run relevant tests per docs/TESTING.md

## Project Status Handoff

`PROJECT_STATUS.md` is the mandatory project-state handoff for future chats and coding agents.

Before finishing any task that changes the real project state, the agent MUST update `PROJECT_STATUS.md`.

Update it when any of the following changes:
- a milestone is completed
- a real-world acceptance test passes or fails
- implementation status materially changes
- a blocker is discovered, changed, or resolved
- the current phase changes
- the next required action changes

Rules:
- Do NOT mark a feature complete merely because code, documentation, or mocked tests exist.
- Record real Windows / Spotify / Siri validation separately from code/spec/mock-test completion.
- If a real-world test was not run, explicitly keep it under Not Yet Proven or equivalent status.
- Keep the file concise and current; remove or replace stale next-step information when superseded.
- Never write secrets, API keys, OAuth tokens, passwords, or private credentials into `PROJECT_STATUS.md`.
- A task that does not change project state (for example, explanation-only work) does not require a status-file edit.

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
- Local LLM integration is allowed in V1 only under the approved safety architecture: rule-first/fallback-only, closed schema, deterministic grounding, no direct execution, and no AI handling of shutdown/force-close/firewall/system-administration actions.
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
- Active maintained specifications are authoritative in this order: `docs/SECURITY.md` → `docs/SPEC.md` → `docs/ARCHITECTURE.md` → task/platform documents.
- `PROJECT_STATUS.md` records current implementation/acceptance state and decisions, but cannot weaken active security requirements.
- `docs/SOURCE_SPEC.md` is a read-only historical snapshot. Keep it for provenance, but do not use it to override newer accepted product/spec/security decisions.
- When historical SOURCE_SPEC text conflicts with the active maintained specifications, follow the active maintained specifications.
