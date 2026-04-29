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

### Companion

The Companion sends compact state snapshots to:

```text
POST /v1/companion/{channel_id}/snapshot
Authorization: Bearer <companion-token>
```

The current prototype includes `companion/fake_companion.py`.

### EBS

The EBS validates the protocol envelope, enforces the 5 KB payload budget,
rate-limits each channel to roughly 1 message per second, signs a Twitch EBS
JWT with the configured extension secret, and sends the message to Twitch
Extension PubSub.

In `EBS_DRY_RUN=1`, it validates and stores the latest state but does not call
Twitch.

### Twitch Extension Frontend

`extension/viewer.html` listens to `broadcast` messages and renders a compact
board using static reference data from `extension/data`.

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

