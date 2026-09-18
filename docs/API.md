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
  `open_app`, `close_app`, `force_close_app`, `open_website`, `spotify_resume`, `spotify_play_track`, `spotify_pause`, `spotify_next`, `spotify_previous`, `volume_up`, `volume_down`, `mute`, `unmute`, `toggle_mute`, `lock`, `request_shutdown`, `confirm_shutdown`, `refresh_apps`

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

## Spotify Playback Flow

Spotify is the only V1 music provider. The API does not accept a provider selector.

### Resume / Pause / Next / Previous

Natural-language commands map to the closed Spotify actions:
- `spotify_resume`
- `spotify_pause`
- `spotify_next`
- `spotify_previous`

### Play a specific track

For requests such as `播放周杰倫的晴天`, the parser produces a validated action with:
- `action = spotify_play_track`
- `track` = user-provided song title
- `artist` = optional user-provided artist name

The service uses `track` / `artist` only as Spotify Catalog search input. The client never sends a Spotify URI, executable path, command, process ID, or arbitrary URL.

Server flow:
1. Validate the closed action.
2. Search Spotify for a track.
3. Rank exact title + artist matches above weaker matches.
4. If confidence is insufficient or several plausible tracks remain, return a clarification/error message instead of guessing.
5. Resolve a trusted Spotify track URI/ID from the Spotify response.
6. Resolve the configured/active Spotify Connect device.
7. Start playback using the trusted Spotify URI.

A successful response may include safe display metadata such as track title and artist, but must not expose OAuth tokens or internal secrets.

Spotify authorization and device behavior are specified in [SPOTIFY.md](SPOTIFY.md).

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
