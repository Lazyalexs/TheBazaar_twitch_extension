# Companion

The local Companion is served as a static page:

```text
https://api.thebazaar-twitch.online/companion.html
```

Local development:

```text
http://127.0.0.1:5173/companion.html
```

It captures the broadcaster's game window with the browser screen capture API,
lets the broadcaster place normalized hover boxes over cards, and publishes a
snapshot to:

```text
POST /v1/companion/{channel_id}/snapshot
```

Required fields:

- `EBS URL`: `https://api.thebazaar-twitch.online`
- `Channel ID`: the broadcaster Twitch channel id
- `Companion Token`: the channel token configured in EBS

The page stores these values in the browser's `localStorage`, not in the
extension code.

The Companion also stores the current card layout in `localStorage`, so the
broadcaster can reload the page without losing manually placed boxes. The hosted
page includes a web app manifest and service worker, allowing supported browsers
to install it as a standalone app.

For live use, the broadcaster can place a box once and then use `Assign
Selected` to bind a different BazaarDB item to that same screen position without
redrawing the box.

## Hover Contract

Viewer hover zones are deterministic:

- each published board item must use an item id that exists in the bundled
  BazaarDB data file;
- each board item must include a normalized `bbox` inside the video frame;
- each automatically recognized item must meet the viewer confidence threshold;
- the viewer does not create fallback boxes.

If an item id is unknown or a box is missing/invalid, that item is skipped
instead of showing a placeholder or a random card.
The same rule applies to future vision recognition: low-confidence matches are
not shown to viewers.

## Automatic Log Companion

For a no-click streamer workflow, use the log Companion instead of the browser
layout editor. It reads the local Unity log and cache files written by The
Bazaar, links live `InstanceId` values to exact `TemplateId` values, maps those
templates to item names, and publishes them as `source: "game"` with
`confidence: 1`.

Default paths on Windows:

```text
%USERPROFILE%\AppData\LocalLow\Tempo Storm\The Bazaar\Player.log
%USERPROFILE%\AppData\LocalLow\Tempo Storm\The Bazaar\Player-prev.log
%USERPROFILE%\AppData\LocalLow\Tempo Storm\The Bazaar\prod\cache\cards.json
```

Dry-run inspection:

```powershell
.\.venv\Scripts\python companion\log_companion.py --once --dry-run
```

Live publishing:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel 274185831 `
  --token <companion-token>
```

The generated hover boxes can be calibrated without changing code:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel 274185831 `
  --token <companion-token> `
  --board-x 0.09 `
  --board-y 0.52 `
  --socket-step 0.075 `
  --small-width 0.105 `
  --box-height 0.2 `
  --pad-x 0.018 `
  --pad-y 0.005
```

For a 720p Twitch/OBS frame, the log Companion now uses the built-in `720p`
box profile by default. The Companion converts these pixel values to normalized
Twitch coordinates before publishing, so the viewer overlay still scales
correctly when the player is resized:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel 274185831 `
  --token <companion-token> `
  --stream-resolution auto `
  --box-profile 720p
```

Use `--stream-resolution auto` to let the Companion try the local The Bazaar
window size first and then fall back to `1280x720`. The exact card identity still
comes from the game log (`InstanceId` -> `TemplateId` -> BazaarDB item), while
the resolution only affects the normalized hover box geometry.

If the OBS/game capture layout needs manual tuning, override the profile values:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel 274185831 `
  --token <companion-token> `
  --stream-resolution 1280x720 `
  --box-profile 720p `
  --board-left-px 20 `
  --board-top-px 371 `
  --socket-step-px 105 `
  --small-width-px 118 `
  --box-height-px 144 `
  --pad-x-px 8 `
  --pad-y-px 4
```

This path avoids image recognition for card identity. If a live card cannot be
linked to a known game template, it is skipped instead of being guessed.

## Current Scope

This is the first working bridge from the game state to Twitch hover tooltips.
The browser Companion is still available for manual layout testing, but the log
Companion identifies live items automatically from local game data. It does not
guess item names from pixels.

The next automation layer can add OBS/WebSocket source transform detection while
keeping the same EBS payload:

```json
{
  "board": [
    {
      "slot": 0,
      "id": "Dishwasher",
      "source": "game",
      "confidence": 1,
      "tier": "gold",
      "bbox": { "x": 0.0094, "y": 0.5097, "w": 0.1047, "h": 0.2111 }
    }
  ]
}
```
