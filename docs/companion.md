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
