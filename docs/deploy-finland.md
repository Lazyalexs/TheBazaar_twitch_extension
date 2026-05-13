# Finland EBS Deployment

Target server:

```text
31.57.93.123
```

This deployment uses a public site domain for pages and an API subdomain for
the EBS and Twitch Extension endpoints:

```text
https://thebazaar-twitch.online/new?lang=ru
https://thebazaar-twitch.online/register?lang=ru
https://api.thebazaar-twitch.online/viewer.html
https://api.thebazaar-twitch.online/config.html
https://api.thebazaar-twitch.online/live.html
https://api.thebazaar-twitch.online/companion.html
https://api.thebazaar-twitch.online/health
https://api.thebazaar-twitch.online/v1/...
```

## DNS

Create `A` records:

```text
thebazaar-twitch.online -> 31.57.93.123
api.thebazaar-twitch.online -> 31.57.93.123
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
EBS_API_URL
EBS_CORS_ORIGINS
```

Use long random Companion tokens. Do not commit `.env.production`.

Keep `EBS_DRY_RUN=1` until Twitch Extension secret and owner ID are configured.
Switch to `EBS_DRY_RUN=0` only when real PubSub should be sent.

## Nginx

The production server uses host `nginx` for public HTTPS and Docker for the EBS
on `127.0.0.1:8000`.

Nginx files:

```text
deploy/nginx/bootstrap.conf
deploy/nginx/thebazaar-twitch.online.conf
deploy/nginx/thebazaar_proxy.conf
```

`certbot` issues and renews certificates for:

```text
api.thebazaar-twitch.online
thebazaar-twitch.online
```

The nginx config rate-limits registration, Companion snapshot ingest, API
polling, and static files separately. `fail2ban` watches SSH and nginx
rate-limit logs.

## Start

From the repository root:

```bash
docker compose -f deploy/docker-compose.prod.yml up -d --build
```

Check:

```bash
curl https://api.thebazaar-twitch.online/health
curl https://thebazaar-twitch.online/new?lang=ru
curl https://thebazaar-twitch.online/register?lang=ru
curl https://api.thebazaar-twitch.online/viewer.html
curl https://api.thebazaar-twitch.online/companion.html
curl https://api.thebazaar-twitch.online/bazaar-art/s.bazaardb.gg/v1/z13.0/88771f1a4ca12107ef301b0544325e893372db75@256.webp?v=6 -I
```

## Twitch Console

Add the API domain to the Twitch Extension URL fetching allowlist before Hosted
Test:

```text
https://api.thebazaar-twitch.online
```

For domain-based local testing in Twitch Developer Console, use:

```text
Testing Base URI: https://api.thebazaar-twitch.online/
Config Path: config.html
Live Config Path: live.html
Video Fullscreen Path: viewer.html
```

The nginx config proxies BazaarDB card art under:

```text
https://api.thebazaar-twitch.online/bazaar-art/...
```

This keeps extension image loading on the same HTTPS origin during Twitch tests.
