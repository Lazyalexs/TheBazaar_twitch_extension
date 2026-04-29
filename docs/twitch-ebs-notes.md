# Twitch EBS Notes

The EBS is inspired by the public HearthSim HDT EBS architecture:

```text
client sends state -> EBS validates -> EBS signs Twitch JWT -> Twitch PubSub
```

The Bazaar version intentionally differs in authentication and domain logic.
HearthSim uses HSReplay OAuth and linked Twitch accounts. This project starts
with a broadcaster Companion token per channel:

```text
channel_id -> companion_token
```

## Required Twitch Values

When leaving dry-run mode, configure:

```text
TWITCH_EXTENSION_CLIENT_ID
TWITCH_EXTENSION_OWNER_ID
TWITCH_EXTENSION_SECRET_BASE64
TWITCH_EXTENSION_VERSION
EBS_DRY_RUN=0
```

The real extension secret must exist only on the EBS server.

Official references:

- Twitch Extensions Reference: https://dev.twitch.tv/docs/extensions/reference/
- Send Extension PubSub Message: https://dev.twitch.tv/docs/api/reference/#send-extension-pubsub-message

## Later Server Setup

The Finland server can host the first production EBS:

```text
31.57.93.123
```

Before Hosted Test or review, add:

1. DNS A record for the chosen API domain.
2. HTTPS certificate with Caddy, nginx plus certbot, or equivalent.
3. Twitch Extension allowlist entry for the EBS URL fetching domain.
4. Production `.env` with Twitch values and channel tokens.

The domain does not have to be `.com`; it only needs to be a public, unique
HTTPS domain accepted in the Twitch Extension allowlist.
