# Architecture

The first EBS-backed prototype uses this runtime path:

```text
The Bazaar / fake state
  -> broadcaster-side Companion
  -> The Bazaar EBS
  -> Twitch Extension PubSub broadcast
  -> Twitch viewer frontend
```

The EBS exists for three reasons:

1. Keep the Twitch Extension secret out of frontend and Companion code.
2. Validate and rate-limit game-state messages before PubSub.
3. Provide a production fallback if Twitch localhost access is blocked.

## Core Components

### BazaarDB Reference Data

`extension/data/items.min.json` is generated from BazaarDB search pages. It is
static frontend data, so viewers do not call BazaarDB while hovering over the
stream. Refresh it with:

```powershell
node tools\sync-bazaardb-data.mjs
```

The generated records include stable lookup aliases: extension slug, BazaarDB
card id, internal card uuid, and display name. This lets a Companion send either
`dishwasher`, a BazaarDB URL id, or the original card uuid.

### Companion

The Companion sends compact state snapshots to:

```text
POST /v1/companion/{channel_id}/snapshot
Authorization: Bearer <companion-token>
```

The current prototype includes:

- `companion/fake_companion.py` for smoke tests.
- `companion/file_companion.py` for publishing a JSON board file containing real
  `id` and normalized `bbox` values.

### EBS

The EBS validates the protocol envelope, enforces the 5 KB payload budget,
rate-limits each channel to roughly 1 message per second, signs a Twitch EBS
JWT with the configured extension secret, and sends the message to Twitch
Extension PubSub.

In `EBS_DRY_RUN=1`, it validates and stores the latest state but does not call
Twitch.

### Twitch Extension Frontend

`extension/viewer.html` listens to `broadcast` messages and renders transparent
hover hotspots over the stream. A tooltip appears only while the viewer hovers a
Companion-provided `bbox`.

`extension/live.html` is currently a broadcaster diagnostics page for checking
EBS health and the latest received state.

## Protocol

All live messages use protocol envelope v1:

```json
{
  "v": 1,
  "type": "snapshot",
  "seq": 1,
  "sentAt": 1770000000000,
  "patch": "13.3-dev",
  "runId": "fake-local-run",
  "payload": {}
}
```

Supported message types:

- `snapshot`
- `diff`
- `heartbeat`
- `reset`
- `error`

For v1, full snapshots at 1 Hz are the simplest reliable path.
