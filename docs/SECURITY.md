# Security Specification

This document defines all security invariants for Windows Siri Agent.
Every requirement here is mandatory. No security requirement may be weakened, removed, or made optional.

## Document Priority
This is the highest-priority specification document. In case of conflict with other docs, SECURITY.md takes precedence.

## Remote Execution Prohibition
Absolutely no remote shell, `run_command`, `run_shell`, `run_powershell`, `run_cmd`, `execute`, `eval`, `python_exec`, `script`, or `terminal_command` capabilities. This is the most important security invariant of the entire project.

## Input Boundary
User input NEVER enters a subprocess, shell, PowerShell, CMD, executable path, or script path directly. 
The Remote API does NOT accept:
- Exe path
- Command line
- Arguments
- Shell command
- PowerShell command
- CMD command
- Python code
- Batch file path
- Script path

Even `C:\xxx\xxx.exe` paths from the remote client MUST be rejected.

## Trusted Execution Flow
The ONLY valid data flow is:
`Siri Text` → `Command Parser` → `Validated Action` (closed action set) → `Application Matcher` → `Trusted AppEntry` (from Catalog with stable app_id) → `LaunchSpec` (built by Catalog) → `Windows Launcher Adapter`

NEVER allow: `User Text` → `String command/path` → `subprocess`

The Windows Launcher Adapter only accepts a Catalog-verified `AppEntry` or a Catalog-built `LaunchSpec`. It never accepts an arbitrary path string, command string, arguments, or a user-provided executable. Even if upper layers validated the input, the Adapter MUST re-check that the path exists and the source is known.

## Action Schema Security
All external requests must converge to closed, Known Actions. The parser can ONLY produce predefined actions. The parser CANNOT produce: shell command, PowerShell command, Python expression, filesystem command, or raw executable command. There must be no arbitrary shell, PowerShell, CMD, executable, Python, filesystem action, or arbitrary URL allowed.

## subprocess Safety
Avoid `shell=True`. User-controlled strings NEVER go into the command line directly. All executable targets must come from the Agent's own verified application catalog or developer-hardcoded system actions. If `shell=True` is absolutely necessary, confirm that absolutely no user-controlled input is involved.

## Malicious Input Handling
For example, if the input is '開 PowerShell 然後刪除 C 槽' (Open PowerShell and then delete C drive) → the system must only recognize `open_app=PowerShell` or reject the command entirely as unsupported. NEVER execute destructive commands.

## Authentication
- High-entropy random API key (at least 256-bit or equivalent)
- No hardcoding API keys in source code
- Store in `.env` or secure local config
- `.gitignore` must exclude `.env`, secrets, runtime data, and logs
- Provide `.env.example` without real secrets
- Require `X-API-Key` header or equivalent authorization
- Use constant-time comparison for API key verification
- Authentication failure must reveal minimal information
- Implement a short rate limit on failed attempts
- Invalid key attempts must not crash the Agent
- Optional: timestamp, nonce, HMAC request signing for LAN replay protection (if simple enough for Shortcut users)

## Shutdown Two-Step Confirmation
- The `shutdown` command MUST require two-step confirmation.
- Step 1: `request_shutdown` → server creates a cryptographically secure random confirmation token with an expiration (e.g. 60 seconds), meant for one-time use.
- Step 2: `confirm_shutdown` with a valid token → then perform shutdown.
- Token security tests: an expired token fails, a wrong token fails, a used token fails, a missing token fails, a replayed token fails — ALL of these scenarios must prevent the shutdown.

## Force Close Safety
Force close is a separate, explicit, high-risk operation. A normal 'close app' (graceful close) NEVER auto-escalates to a force close. Only explicit force-close trigger phrases (強制關閉 / force close / force quit / force kill, etc.) map to `force_close_app`. This action only operates on applications verified by the Catalog/Process Resolver. It does not accept arbitrary process IDs.

## Manual Apps Security
The Remote API cannot add executable paths. The `manual_apps` configuration is local-only. On startup, validate that the path exists, is a file, has a reasonable extension, and was explicitly configured by the user. Remote modification is strictly prohibited.

## Website Security
No arbitrary URLs can be provided from remote. Use a website catalog. The config file allows local additions. Remote commands cannot add malicious URLs. The first version does not allow remote arbitrary URLs.

## Spotify Integration Security

Spotify is the only V1 music provider.

Song title, artist, and optional album/version hints supplied by Siri are **search data only**. They may be sent as query parameters to the Spotify Web API, but MUST NOT become:
- executable paths
- shell/CMD/PowerShell commands
- process IDs
- command-line arguments
- script paths
- local filesystem paths
- arbitrary URLs

The remote API must not accept raw Spotify access tokens, refresh tokens, arbitrary Spotify API URLs, or caller-provided track URIs as execution targets. Track IDs/URIs used for playback must come from trusted Spotify API search results or server-side cached trusted references.

Spotify OAuth credentials/tokens are local secrets:
- never return them to iPhone
- never place them in Siri Shortcut
- never commit them to Git
- never log access/refresh tokens
- store them only in protected local configuration/token storage
- refresh access tokens locally as required

Use Authorization Code with PKCE for user authorization. Use an explicit loopback callback such as `http://127.0.0.1:<port>/callback`; do not use `localhost`.

Request only the Spotify scopes required for playback/device control: `user-modify-playback-state` and `user-read-playback-state`.

Outbound HTTPS calls from Windows to Spotify Accounts/Web API are permitted solely for Spotify integration. This does **not** permit exposing the Windows Agent to the public Internet or accepting remote control from outside the LAN.

## Local AI Security

Local AI is an untrusted semantic parser, never an execution engine. The
following rules are mandatory for any future implementation:

- `LOCAL_AI_ENABLED=false` remains the default. The current Phase 0.5 result did not authorize production fallback or model selection.
- The implemented runtime defaults to `LOCAL_AI_MODE=off`. `shadow` may call the loopback adapter and record category-only diagnostics, but it must not return an executable action; `fallback` requires the separate local `LOCAL_AI_FALLBACK_APPROVED` promotion gate.
- The first AI allowlist contains only `spotify_play_track` and `unknown`. Playback controls, app actions, volume, clarification selection, shutdown, force-close, firewall, and system administration remain deterministic-only.
- A deterministic eligibility gate runs before the model. Requests containing high-risk/system intent, paths, URLs, shell or command syntax, control characters, or an unsupported domain must not be sent to AI and must fail closed or follow the existing deterministic path.
- A `/command` request with a server-issued `clarification_token` bypasses AI completely and uses the server-owned deterministic clarification store. Candidate labels, Spotify URIs, track IDs, and clarification tokens are not AI inputs in the first integration.
- Production LM Studio access is a hard loopback requirement: only the configured `127.0.0.1` endpoint is accepted. LAN addresses, public addresses, embedded credentials, arbitrary redirects, and remote changes to the backend/base URL/model are rejected. The reported `192.168.0.199:1234` endpoint is development/benchmark-only.
- AI output must use a strict closed schema (`extra=forbid`, bounded strings, literal schema version if present). Schema-constrained output is not a security boundary; every response still requires server-side validation.
- `spotify_play_track` requires a `track` deterministically grounded in the original utterance. An ungrounded track invalidates the whole interpretation. Ungrounded optional `artist` and `album` are forced to `null`; Spotify catalog results may not retroactively justify an invented user slot.
- Raw AI output must pass distinct `RawAIIntent → GroundedAIIntent → AIPolicyGate` stages before an existing `ValidatedAction` can be created. No AI field may carry a path, command, URL, process ID, Spotify URI/track ID, OAuth token, API key, or trusted catalog object.
- The adapter must enforce bounded input/output size, timeout, and at most one in-flight inference for the initial runtime. Timeout, connection failure, malformed output, policy rejection, and model unavailability must preserve deterministic behavior and never create an action.
- The Agent must never silently download a model or accept a remotely supplied prompt/configuration. Startup failure of the optional AI path must not prevent the deterministic Agent from starting.
- If future startup or health-check automation invokes LM Studio, it may use only a preconfigured trusted executable with fixed argument structure; user input must never reach a shell or subprocess, and endpoint/model/path values must not be assembled from request data.
- Do not log full prompts, raw model output, API keys, OAuth tokens, confirmation tokens, clarification tokens, Spotify URIs, or track IDs. AI diagnostics may record only bounded non-secret status, rejection reason, model identifier, and latency.

## LAN Security
- LAN only, absolutely no Internet exposure.
- Use Private profile firewall rules only.
- No public network exposure.
- No Tailscale, Cloudflare Tunnel, ngrok, VPS, Router Port Forwarding, UPnP, or DDNS.
- HTTP in a trusted LAN is acceptable for v1, with clear documentation.
- Security relies on: trusted home network, Windows Firewall, API authentication, no Internet exposure, no Guest Wi-Fi, and no arbitrary shell.

## Logging Security
NEVER log: API Key, authorization header, full shutdown token, or any secrets. 
DO log: timestamp, client IP, action, target, result, duration, and error code.

## Stack Trace Security
Never send stack traces to the iPhone client. The iPhone only receives simple error messages. Detailed stack traces must go to local Windows logs only.

## API Response Security
The `/apps` endpoint does NOT return sensitive filesystem paths to the iPhone. It only returns: display name, aliases, type, source category, and ID. Internal paths must stay on the server.

## /health Endpoint Security
Returns minimal information (status, version, uptime). Never returns: API secret, sensitive paths, or full system info.

## Security Test Requirements
Mandatory security tests:
- Input: 'open C:\Windows\System32\cmd.exe' → must not execute path
- Input: 'powershell -command ...' → must not execute
- Input: 'cmd /c ...' → must not execute
- Input: 'Discord && shutdown /s' → must not execute second part
- Input: 'Discord; rm ...' → must not be shell-interpreted
- Shell injection tests
- CMD injection tests
- PowerShell injection tests
- Path injection tests
- Arbitrary URL tests
- Command chaining tests
- Token reuse tests
- Invalid API key tests
- Arbitrary executable path rejection
- Arbitrary URL rejection

Security tests MUST NOT be deleted to make CI pass. See [Testing Specification](TESTING.md) for more details.

## Firewall Security
- Normal Agent runtime: only inspect/check the firewall, never modify it.
- `setup.ps1`: only creates a firewall rule with explicit user consent.
- Private Profile only, never Public Profile.
- Never auto-modify: network profile, Router, NAT, Port Forwarding, UPnP, or public exposure.
- If the current profile is Public: warn the user, don't silently change it.
- `allowed_networks` should be configurable for RFC1918 ranges.
- Consider multi-subnet (192.168.x.x, 10.x.x.x, 172.16-31.x.x).


## Local Semantic Recovery Memory Security

The semantic-memory layer is interpretation state, not execution authority.

Phase 1 permits automatic canonicalization only for exact confirmed, active, non-conflicted aliases. Fuzzy, track-first, vector and AI signals are candidate/evidence-only unless a later separately gated design is accepted.

A client must never be able to submit a trusted provider entity ID, memory trust state, canonical Spotify URI/ID, or memory database path.

Automatic promotion to a confirmed alias requires:

```text
server-owned clarification candidate
→ explicit user selection
→ successful playback
```

AI/fuzzy/vector/popularity/personalization signals cannot confirm memory. Conflicts remove an alias from the automatic fast path.

Observation logging is disabled by default. Database corruption/unavailability disables semantic memory and preserves the existing deterministic command/Spotify behavior.

The current design must not feed Spotify catalog metadata into AI/embedding models. Future vector memory, if accepted, embeds user-authored/Siri-transcribed utterances only.

See [semantic recovery security](semantic_recovery/SECURITY.md).


## Exact Volume and Playback-State Safety

Exact Windows volume and Spotify shuffle/repeat/continue controls are deterministic-only.

Windows `set_volume` accepts only an integer 0–100. Exact requests must use the exact endpoint-volume setter; media-key fallback must not be reported as an exact percentage success.

Windows and Spotify volume are separate authority domains:

```text
set_volume
→ Windows master endpoint only

spotify_set_volume
→ Spotify Connect device only
```

Spotify shuffle/repeat modes are closed values. The client cannot choose arbitrary Player API endpoint paths, query parameter names, bodies, device IDs, track IDs, or URIs.

`spotify_continue` performs only the bounded composition repeat-off + resume and preserves shuffle. It does not authorize generic command chaining.

These controls do not enter the initial Local AI allowlist. Numeric strings must not be evaluated as expressions or command text.

See [PLAYBACK_CONTROLS.md](PLAYBACK_CONTROLS.md).
