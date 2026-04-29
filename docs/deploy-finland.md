# Finland EBS Deployment

Target server:

```text
31.57.93.123
```

This file is a deployment checklist for later. The current local prototype does
not require the domain or certificates yet.

## DNS

Create an `A` record:

```text
api.<your-domain> -> 31.57.93.123
```

The domain does not have to be `.com`.

## Server Packages

On the server:

```bash
apt update
apt install -y git docker.io docker-compose-plugin
systemctl enable --now docker
```

## Environment

Copy `.env.production.example` to `.env.production` and fill:

```text
TWITCH_EXTENSION_CLIENT_ID
TWITCH_EXTENSION_OWNER_ID
TWITCH_EXTENSION_SECRET_BASE64
TWITCH_EXTENSION_VERSION
COMPANION_TOKENS_JSON
EBS_PUBLIC_URL
EBS_CORS_ORIGINS
```

Use long random Companion tokens. Do not commit `.env.production`.

## Caddy

Copy `deploy/caddy/Caddyfile.example` to `deploy/caddy/Caddyfile` and replace
`api.example.com` with the real API domain.

Caddy will request and renew certificates automatically after DNS points to the
server.

## Start

From the repository root:

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Check:

```bash
curl https://api.<your-domain>/health
```

## Twitch Console

Add the API domain to the Twitch Extension URL fetching allowlist before Hosted
Test:

```text
https://api.<your-domain>
```

The extension frontend files still need to be packaged and configured in Twitch
Developer Console separately.

