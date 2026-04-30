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
- the viewer does not create fallback boxes.

If an item id is unknown or a box is missing/invalid, that item is skipped
instead of showing a placeholder or a random card.

## Current Scope

This is the first working bridge from the game screen to Twitch hover tooltips.
It does not yet identify items automatically from pixels. The broadcaster still
selects the BazaarDB item and places the box manually.

The next automation layer should replace manual selection with screen
recognition while keeping the same EBS payload:

```json
{
  "board": [
    {
      "slot": 0,
      "id": "dishwasher",
      "tier": "gold",
      "bbox": { "x": 0.315, "y": 0.52, "w": 0.112, "h": 0.2 }
    }
  ]
}
```
