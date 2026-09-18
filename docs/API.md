# API Contract

API contract definitions only — no server implementation.

All endpoints except `/health` require authentication.

See [Security](SECURITY.md#authentication) for full requirements.

## GET /health

- No authentication required
- Returns minimal: status (ok), version, uptime
- NEVER returns: API secret, sensitive paths, full system info

## GET /info

- Returns version, system info
- Requires authentication

## GET /apps

- Requires authentication
- Lists discovered applications
- Does NOT return sensitive filesystem paths
- Returns: display_name, aliases, type, source category, app_id
- Internal paths stay on server

See [Security](SECURITY.md#api-response-security)

## POST /apps/search

- Requires authentication
- Input: search text (e.g. 'photoshop')
- Returns: best match, confidence, candidates, whether ambiguous

## POST /apps/refresh

- Requires authentication
- Rebuilds application catalog
- No need to restart Agent after installing new programs

## POST /action

- Requires authentication
- Accepts structured safe operations:
  `open_app`, `close_app`, `force_close_app`, `open_website`, `media_play_pause`, `media_next`, `media_previous`, `volume_up`, `volume_down`, `mute`, `unmute`, `toggle_mute`, `lock`, `request_shutdown`, `confirm_shutdown`, `refresh_apps`

## POST /command

- Requires authentication
- Main Siri API
- Input: text (natural language)
- Agent parses internally
- All command parsing on Windows Agent, not Apple Shortcut

## Response Schema

Unified response:
- `success` (bool)
- `status`
- `action`
- `message` (for Siri to speak)
- `candidates` (for ambiguous app results)
- `clarification_required` (bool; for safe follow-up questions such as choosing a media provider)
- `clarification_type` (e.g. `media_provider`)
- `options` (allowlisted choices only; never executable paths/commands/URLs)
- `confirmation_required` (bool)
- `confirmation_token` (for shutdown flow)
- `error_code`

## Media Provider Clarification Flow

When `POST /command` receives a bare playback request such as `播放`, `播放音樂`, or `Play` without a provider:

1. Agent does not guess a provider and does not immediately dispatch an unrestricted launch.
2. Return `clarification_required=true`, `clarification_type="media_provider"`, a Siri-friendly `message`, and allowlisted `options`.
3. V1 provider allowlist: `youtube_music`, `apple_music`, `spotify`.
4. The Shortcut asks the user to choose/say one of those providers.
5. The follow-up request sends only the selected provider identifier or equivalent natural-language phrase back to the Agent.
6. Agent validates the provider against the closed allowlist, resolves it through trusted internal mappings/catalog entries, then performs playback best-effort.
7. Arbitrary provider strings, executable paths, command arguments, or URLs are rejected.

Example clarification response:

```json
{
  "success": false,
  "status": "clarification_required",
  "action": "play",
  "message": "要使用 YouTube Music、Apple Music，還是 Spotify？",
  "clarification_required": true,
  "clarification_type": "media_provider",
  "options": [
    {"id": "youtube_music", "label": "YouTube Music"},
    {"id": "apple_music", "label": "Apple Music"},
    {"id": "spotify", "label": "Spotify"}
  ],
  "confirmation_required": false,
  "error_code": null
}
```

If the original command already names an allowlisted provider (for example `播放 Spotify`), the clarification step is skipped.

`pause`, `media_next`, and `media_previous` continue to target the current active media session by default.

Don't make iPhone parse many different formats.

## Error Schema

Defined error types:
Invalid API key, Missing API key, Invalid command, Unknown app, Ambiguous app, App launch failure, App close failure, Website not found, Media control failure, Volume failure, Shutdown token expired/reused/invalid, Firewall issue, Network issue, Catalog unavailable, Malformed request

## Shutdown Confirmation Flow

1. Client sends command '關機' → `POST /command`
2. Server returns: `confirmation_required=true`, `message='確定要關閉電腦嗎？'`, `confirmation_token=<token>`
3. Client shows confirmation dialog
4. If confirmed: `POST /action` with `action=confirm_shutdown`, `token=<token>`
5. Server validates token (not expired, not used, correct) → shutdown

See [Security](SECURITY.md#shutdown-two-step-confirmation) for token security requirements.

## Rate Limiting

- Simple per-IP per-minute limit
- Don't block normal Siri usage
- Applied at infrastructure/middleware layer
