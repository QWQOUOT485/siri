# Deterministic Volume and Spotify Playback Controls

**Status:** Approved for implementation  
**Date:** 2026-09-19

This document defines deterministic closed actions for exact Windows master-volume control and extended Spotify playback-state control.

These controls are **not Local AI features**. They must be parsed and validated deterministically.

---

## 1. Design goals

The user should be able to say natural commands such as:

```text
音量調到 37%
把音量降到 25%
聲音設成 80%
set volume to 45 percent

單曲循環
一直重複這首
循環播放清單
關閉循環

隨機播放
不要隨機

就一直播下去
正常播就好
```

The Agent must convert these phrases into closed, bounded actions. No command may become shell text, arbitrary HTTP, executable arguments, or arbitrary Spotify request bodies.

---

## 2. Windows master volume: exact percentage

### 2.1 New action

Add:

```text
set_volume
```

with a bounded field:

```text
volume_percent: integer 0..100
```

This action means **Windows master endpoint volume**, not Spotify Connect device volume.

Existing relative actions remain:

```text
volume_up
volume_down
mute
unmute
toggle_mute
```

### 2.2 Target phrases

Chinese examples:

```text
音量 30
音量 30%
音量調到 30
音量調到 30%
把音量調成 30%
把音量降到 25%
把音量提高到 80%
聲音設成 50%
```

English examples:

```text
volume 30
volume 30 percent
set volume to 30
set volume to 30 percent
set system volume to 30 percent
```

The parser must distinguish absolute target percentage from relative changes such as:

```text
音量降低
音量小一點
volume down
```

### 2.3 Validation

Only integer values from 0 through 100 are valid.

Reject:

```text
-1
101
1000
NaN
infinity
arbitrary expressions
```

Do not evaluate arithmetic expressions from the client.

### 2.4 Execution

Preferred Windows implementation:

```text
pycaw endpoint
→ SetMasterVolumeLevelScalar(volume_percent / 100)
```

The exact-set action changes the scalar volume level only. It does **not** silently toggle the endpoint mute bit. Mute/unmute remain separate explicit actions.

### 2.5 Exact-volume fallback rule

Media-key fallback can only perform relative increments/decrements; it cannot reliably guarantee an exact arbitrary percentage.

Therefore:

```text
set_volume + pycaw available
→ set exact scalar

set_volume + pycaw unavailable/fails
→ return explicit exact-volume failure
→ DO NOT approximate by sending media keys
```

Relative `volume_up` / `volume_down` may retain their existing media-key fallback.

### 2.6 Suggested result

On success, return a bounded normalized level, for example:

```json
{
  "level": 0.37,
  "percent": 37
}
```

No device internals or sensitive paths are returned.

---

## 3. Windows vs Spotify volume

These are different control planes and must remain separate.

```text
音量 30%
→ Windows master volume

Spotify 音量 30%
→ Spotify Connect device volume
```

Do not silently reinterpret one as the other.

Suggested Spotify action remains:

```text
spotify_set_volume
spotify_volume_percent: integer 0..100
```

Spotify exact volume is executed only through the fixed Spotify Player API endpoint and existing OAuth/trusted-device flow.

---

## 4. Spotify shuffle

Closed actions:

```text
spotify_shuffle_on
spotify_shuffle_off
```

Examples:

```text
隨機播放
開啟隨機播放
打亂播放
shuffle on

不要隨機
關閉隨機播放
shuffle off
```

Execution maps to the fixed Spotify Player API shuffle state endpoint.

Only a boolean state is permitted. The client never controls an endpoint URL, query name, device ID, or arbitrary body.

---

## 5. Spotify repeat

Closed actions:

```text
spotify_repeat_track
spotify_repeat_context
spotify_repeat_off
```

Semantics:

```text
spotify_repeat_track
→ repeat current track

spotify_repeat_context
→ repeat current playback context (playlist/album/etc.)

spotify_repeat_off
→ disable repeat
```

Examples:

```text
單曲循環
重複這首
一直重複這首
repeat this track

循環播放
循環這張專輯
循環這個播放清單
repeat playlist
repeat context

不要重複
關閉循環
取消循環
repeat off
```

The parser must not treat "隨機" and "循環" as the same state.

---

## 6. Spotify continue / normal continuous playback

Add a convenience closed action:

```text
spotify_continue
```

Target phrases:

```text
就一直播下去
正常播就好
照順序繼續播
繼續正常播放
continue normally
keep playing normally
```

Defined behavior:

```text
repeat = off
→ resume playback
→ preserve current shuffle state
```

Important:

- `spotify_continue` does **not** force shuffle off.
- It does not rebuild or invent a queue.
- It does not promise infinite playback beyond what the current Spotify context/queue makes available.
- It means "disable repeat and continue normal playback in the current context."

If the user explicitly says:

```text
照順序播 / 不要隨機
```

that should additionally select `spotify_shuffle_off`; do not infer it from generic "繼續播".

---

## 7. Existing/future deterministic Spotify controls

The same closed-action family should also keep the already-planned controls:

```text
spotify_seek
spotify_set_volume
spotify_like_current
spotify_unlike_current
```

Bounds:

- seek: non-negative bounded milliseconds derived by parser
- Spotify volume: integer 0..100
- like/unlike: only the server-resolved currently playing Spotify track
- no client-provided Spotify URI/track ID

---

## 8. Domain model changes

Suggested action vocabulary:

```text
set_volume

spotify_shuffle_on
spotify_shuffle_off

spotify_repeat_track
spotify_repeat_context
spotify_repeat_off

spotify_continue

spotify_seek
spotify_set_volume
spotify_like_current
spotify_unlike_current
```

Suggested bounded action fields:

```text
volume_percent: int | None        # Windows master only, 0..100
spotify_volume_percent: int | None # Spotify device only, 0..100
seek_ms: int | None               # Spotify seek only, bounded non-negative
```

The validation model must reject fields on unrelated actions.

Examples:

```text
set_volume + spotify_volume_percent
→ invalid

spotify_set_volume + volume_percent
→ invalid

spotify_repeat_track + seek_ms
→ invalid
```

---

## 9. Service/adaptor responsibilities

### CommandParser

Owns deterministic recognition of the closed phrases and numeric bounds.

### WindowsVolumeController

Owns:

```text
relative volume
mute state
exact Windows scalar volume
```

It does not know Spotify.

### SpotifyService

Owns orchestration for shuffle/repeat/continue/seek/device-volume/like-unlike.

### Spotify player adapter

Owns fixed Spotify HTTP transport only.

It must not accept arbitrary endpoint paths or arbitrary JSON/query payloads from the client/parser.

---

## 10. Local AI boundary

These controls stay deterministic-only in the first production design.

Local AI should not parse or execute:

```text
set_volume
spotify_shuffle_*
spotify_repeat_*
spotify_continue
spotify_seek
spotify_set_volume
spotify_like_current
spotify_unlike_current
```

Reason:

- the grammar is bounded;
- numeric/state validation is simple;
- deterministic behavior is faster and safer;
- AI adds no useful authority here.

---

## 11. Error handling

### Windows exact volume

Possible explicit errors:

```text
INVALID_VOLUME_PERCENT
WINDOWS_ONLY
NON_INTERACTIVE_SESSION
EXACT_VOLUME_UNAVAILABLE
VOLUME_CONTROL_FAILED
```

Do not claim success when only an approximate media-key fallback was possible.

### Spotify playback state

Keep existing Spotify handling:

- 401 → refresh token, then re-auth if necessary
- 403 → permission/Premium/account-state message
- 429 → respect Retry-After; no busy loop
- no active/usable device → explicit device error
- transport failure → safe failure; no alternate arbitrary HTTP path

---

## 12. Parser ambiguity rules

The parser must prefer explicit bounded forms.

Examples:

```text
音量降低
→ volume_down

音量降低到 30%
→ set_volume(30)

Spotify 音量降低
→ unsupported unless an explicit relative Spotify-volume action is separately designed

Spotify 音量 30%
→ spotify_set_volume(30)
```

Repeat examples:

```text
重複這首
→ spotify_repeat_track

循環播放清單
→ spotify_repeat_context

不要循環
→ spotify_repeat_off
```

Continue examples:

```text
繼續播放
→ existing spotify_resume

正常播就好
→ spotify_continue (repeat off + resume)

不要隨機，繼續播放
→ if compound commands remain unsupported, reject rather than executing half
```

Do not introduce generic command chaining just to support these controls.

---

## 13. Required unit tests

### Windows exact volume

- parse Chinese exact percentages
- parse English exact percentages
- 0 accepted
- 100 accepted
- -1 rejected
- 101 rejected
- absolute form wins over relative verb wording
- `ValidatedAction` rejects `volume_percent` on unrelated actions
- pycaw exact setter receives 0.00 / 0.37 / 1.00 correctly
- exact-set failure does not use media-key approximation
- exact volume does not silently toggle mute
- existing relative step fallback remains unchanged

### Spotify shuffle

- on/off parser phrases
- boolean-only service call
- 401/403/429 handling
- no arbitrary endpoint/body control

### Spotify repeat

- track/context/off parser phrases
- closed enum/state mapping only
- no free-form repeat mode reaches adapter

### Spotify continue

- repeat off is requested
- playback resumes
- shuffle state is preserved
- it does not invent queue/context
- failure of repeat/resume is surfaced deterministically

### Spotify device volume

- accepts 0..100
- rejects out-of-range
- clearly distinct from Windows `set_volume`

### Security

- numeric fields cannot contain expressions/commands
- command chaining remains rejected
- no new arbitrary URL/path/shell fields
- Local AI cannot emit these control actions in its initial allowlist

---

## 14. Runtime acceptance

Safe real-device checks:

```text
Windows:
set 0%
set 25%
set 50%
set 100%
restore user's preferred level

Spotify:
shuffle on/off
repeat track/context/off
spotify_continue
Spotify device volume at a safe value
```

Do not perform destructive operations.

Verify Siri wording and API responses separately from mocked unit tests.

---

## 15. Implementation order

Recommended deterministic-controls batch:

```text
1. domain action schema
2. parser exact Windows volume
3. Windows exact volume adapter/service wiring
4. Spotify shuffle
5. Spotify repeat
6. Spotify continue
7. Spotify seek/device volume
8. like/unlike current track
9. unit/security tests
10. safe Windows/Spotify/Siri acceptance
11. status/docs update from planned → implemented only after verification
```

Do not label any item implemented until source tests and the relevant runtime acceptance actually pass.
