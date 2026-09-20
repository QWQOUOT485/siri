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
  `open_app`, `close_app`, `force_close_app`, `open_website`, `spotify_resume`, `spotify_play_track`, `spotify_pause`, `spotify_next`, `spotify_previous`, `spotify_shuffle_on`, `spotify_shuffle_off`, `spotify_repeat_off`, `spotify_repeat_track`, `spotify_repeat_context`, `spotify_continue`, `volume_up`, `volume_down`, `set_volume`, `mute`, `unmute`, `toggle_mute`, `lock`, `request_shutdown`, `confirm_shutdown`, `refresh_apps`

## POST /command

- Requires authentication
- Main Siri API
- Input: `text` (natural language), plus optional server-issued `clarification_token` for a second-turn Spotify selection
- Agent parses internally
- All command parsing on Windows Agent, not Apple Shortcut
- If `clarification_token` is present, the request is handled directly by the server-owned deterministic Spotify clarification store; it does not invoke Local AI and does not accept a client-provided track ID or URI.

When the response has `clarification_required=true`, the client may send the
spoken follow-up and the returned opaque token back to this same endpoint:

```json
{
  "text": "第二首",
  "clarification_token": "opaque-short-lived-token"
}
```

The token is short-lived and one-use. The client cannot use it to submit a
Spotify URI or track ID; selection is restricted to the server-created
candidate set. An unclear follow-up may retain the same token only while its
bounded attempt/TTL policy permits it.

## Response Schema

Unified response:
- `success` (bool)
- `status`
- `action`
- `message` (for Siri to speak)
- `candidates` (for ambiguous app results)
- `clarification_required` (bool; currently used for deterministic Spotify track selection)
- `clarification_type` (currently `spotify_track` when clarification is required)
- `clarification_token` (opaque, short-lived server token; only present when required)
- `options` (at most three safe display labels; never executable paths/commands/URLs, Spotify URIs, or track IDs)
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
- `album` = optional parenthesized album/version hint, for example `葉惠美`

The service uses `track` / `artist` / `album` only as Spotify Catalog search input. The client never sends a Spotify URI, executable path, command, process ID, or arbitrary URL.

Server flow:
1. Validate the closed action.
2. Search Spotify for a track.
3. Rank exact title + artist matches above weaker matches.
4. Exclude Live/Concert/Tour/演唱會/現場 candidates. If confidence is insufficient or several plausible tracks remain, return at most three trusted candidates and a short-lived clarification token instead of guessing.
5. Resolve a trusted Spotify track URI/ID from the Spotify response.
6. Resolve the configured/active Spotify Connect device.
7. Start playback using the trusted Spotify URI.

A successful response may include safe display metadata such as track title and artist, but must not expose OAuth tokens or internal secrets.

Spotify authorization and device behavior are specified in [SPOTIFY.md](SPOTIFY.md).

Don't make iPhone parse many different formats.

## Error Schema

Defined error types:
Invalid API key, Missing API key, Invalid command, Unknown app, Ambiguous app, App launch failure, App close failure, Website not found, Media control failure, Volume failure, Shutdown token expired/reused/invalid, Spotify clarification expired/used/unclear/attempts exhausted, Firewall issue, Network issue, Catalog unavailable, Malformed request

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

## Spotify Authorization and Status

- `GET /spotify/status` — requires authentication; returns only local authorization status, scope, and expiry metadata.
- `GET /spotify/auth/start` — requires authentication; returns a Spotify PKCE authorization URL.
- `GET /spotify/callback` — loopback-only OAuth callback; it never returns or logs tokens.

Spotify access and refresh tokens remain in the Windows `runtime` directory. iPhone/Siri only sends natural-language text to `/command` and never receives a token.


## Deterministic exact volume and playback-state commands

These commands continue to arrive through the normal authenticated `POST /command` text interface. The client does not receive a generic action-execution API.

Supported target language after implementation:

```text
音量調到 37%
Spotify 音量 40%
隨機播放
關閉隨機播放
單曲循環
循環播放清單
關閉循環
正常播就好
```

Server-side parsed actions are closed/bounded:

```text
set_volume(volume_percent=0..100)
spotify_set_volume(spotify_volume_percent=0..100)
spotify_shuffle_on/off
spotify_repeat_track/context/off
spotify_continue
```

The HTTP client cannot submit arbitrary Spotify URL/URI/track ID, arbitrary repeat state, arbitrary JSON body, Windows audio endpoint object, or shell command through these features.

`spotify_continue` means repeat off + resume and preserves the current shuffle state.

See [PLAYBACK_CONTROLS.md](PLAYBACK_CONTROLS.md) for the implementation contract.
