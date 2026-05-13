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
- `Twitch Nick`: the broadcaster Twitch channel nickname
- `Companion Token`: the channel token configured in EBS

Streamer registration:

- Open `https://thebazaar-twitch.online/register?lang=ru`.
- Enter Twitch Nick, email, and language.
- Copy the returned `Twitch Nick` and `Companion Token` into the desktop app.
- Press `Verify` before starting the publisher.

The token is shown once and then stored only as a hash on the EBS. If a streamer
loses it, issue a new token from the registration page. When SMTP is configured
on the EBS, the same `Twitch Nick` and `Companion Token` are emailed to the
streamer after registration. Servers with blocked outbound SMTP can use
`EBS_MAIL_PROVIDER=yandex_postbox` to send registration emails through Yandex
Cloud Postbox over HTTPS.

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

- each board item must include a normalized `bbox` inside the video frame;
- each automatically recognized item must meet the viewer confidence threshold;
- known cards should use an item id that exists in the bundled BazaarDB data
  file;
- cards that exist in the game log but do not expose a `TemplateId` are
  published as `unknown:<InstanceId>` so the viewer still shows their hover box.

If a box is missing/invalid, that item is skipped instead of showing a random
card. Unknown game-log cards show a generic tooltip until the log exposes an
exact template.
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

## Windows Streamer App

The desktop streamer app wraps the log Companion into a normal Windows UI:

```powershell
.\.venv\Scripts\python -m companion.desktop_app
```

It provides:

- EBS URL, Twitch Nick, and Companion Token setup;
- registration page shortcut and token verification;
- Russian and English UI language selection;
- secure token storage with Windows DPAPI under the current Windows account;
- HTTPS enforcement for remote EBS URLs;
- Start, Stop, and Test Once controls;
- live status for server publishing, game phase, board cards, and basic run
  statistics from the local log;
- 1080p box profile by default for standard Twitch streams.

Build the `.exe`:

```powershell
.\companion\build_windows.ps1
```

The executable is written to:

```text
dist\TheBazaarLiveBoardCompanion\TheBazaarLiveBoardCompanion.exe
```

Dry-run inspection:

```powershell
.\.venv\Scripts\python companion\log_companion.py --once --dry-run
```

Live publishing:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel twitch_nick `
  --token <companion-token>
```

The generated hover boxes can be calibrated without changing code:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel twitch_nick `
  --token <companion-token> `
  --board-x 0.015625 `
  --board-y 0.5153 `
  --socket-step 0.08203 `
  --small-width 0.07 `
  --medium-width 0.1125 `
  --large-width 0.16875 `
  --box-height 0.2 `
  --pad-x 0.005 `
  --pad-y 0.0037
```

For a standard 1080p Twitch/OBS frame, the log Companion now uses the built-in `1080p`
box profile by default. The Companion converts these pixel values to normalized
Twitch coordinates before publishing, so the viewer overlay still scales
correctly when the player is resized:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel twitch_nick `
  --token <companion-token> `
  --stream-resolution auto `
  --box-profile 1080p
```

Use `--stream-resolution auto` to let the Companion try the local The Bazaar
window size first and then fall back to `1920x1080`. The exact card identity still
comes from the game log (`InstanceId` -> `TemplateId` -> BazaarDB item), while
the resolution only affects the normalized hover box geometry.
Built-in profiles use the game item size to shape hover boxes: small items are
narrow, medium items are square-ish, and large items are wide rectangles. The
desktop app shows calibration fields directly in the main window for tuning the
streamer's actual OBS/game capture layout: `Left px`, `Top px`, `Opp Top`,
`Step px`, `Small W`, `Medium W`, `Large W`, `Height`, `Pad X`, and `Pad Y`.
Opponent combat cards are added to the same `board` payload for compatibility
with already deployed EBS/viewer builds. They use the same left/step/size values
with their own `Opp Top` vertical position.
`Visual fallback for unknown cards` can stay enabled for streamer builds; it only
runs when the log reports a card without a template id. The visual fallback now
requires the best art match to be clearly better than the runner-up, so visually
similar variants stay as `unknown:<InstanceId>` instead of being published as the
wrong card.
Unchanged state is republished every 15 seconds by default, so EBS recovers
automatically after a server restart.

If the OBS/game capture layout needs manual tuning, override the profile values:

```powershell
.\.venv\Scripts\python companion\log_companion.py `
  --url https://api.thebazaar-twitch.online `
  --channel twitch_nick `
  --token <companion-token> `
  --stream-resolution 1920x1080 `
  --box-profile 1080p `
  --board-left-px 30 `
  --board-top-px 556.5 `
  --socket-step-px 157.5 `
  --small-width-px 132 `
  --medium-width-px 216 `
  --large-width-px 324 `
  --box-height-px 216 `
  --pad-x-px 9 `
  --pad-y-px 4.5
```

This path avoids image recognition for card identity. If a live card cannot be
linked to a known game template, it is still published with a calibrated hover
box as `unknown:<InstanceId>` instead of being guessed as the wrong card.
Opponent board entries currently come from `[Opponent] [Hand]` log snapshots.
The game log does not expose opponent `TemplateId` values, so those cards are
resolved by visual fallback when the screenshot match is strong; otherwise they
remain visible as unknown hover boxes.

The desktop app can also enable a visual fallback for those unknown game-log
cards. It captures the local The Bazaar window, crops the unknown card's hover
box, compares it against cached BazaarDB art from `extension/data/items.min.json`,
and publishes the card as `source: "vision"` only when the best match is above
the confidence threshold and the score gap to the second-best match is large
enough. This fallback is used only for cards that do not have `InstanceId ->
TemplateId` in the log.

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
      "bbox": { "x": 0.0109, "y": 0.5111, "w": 0.0781, "h": 0.2083 }
    }
  ]
}
```
