# The Bazaar Twitch Extension

Prototype monorepo for a Twitch Extension and EBS that can broadcast live
The Bazaar state from a broadcaster-side Companion to Twitch viewers.

The EBS shape follows the same broad pattern as HearthSim's HDT EBS:

```text
Companion -> EBS -> Twitch Extension PubSub -> Viewer Extension
```

The implementation here is written specifically for The Bazaar and does not
copy HearthSim code.

## Current Local Prototype

```text
extension/   Twitch Extension frontend files
ebs/         FastAPI EBS that validates Companion snapshots and sends PubSub
companion/   Fake/file Companion senders for local testing
docs/        Architecture and setup notes
```

Windows streamer app:

```powershell
.\.venv\Scripts\python -m companion.desktop_app
```

Build a local `.exe`:

```powershell
.\companion\build_windows.ps1
```

Start with dry-run mode before Twitch secrets and HTTPS are configured:

```powershell
Copy-Item .env.example .env
.\tools\dev.ps1
```

In another terminal:

```powershell
.\.venv\Scripts\python companion\fake_companion.py --once
```

Health check:

```text
http://127.0.0.1:8000/health
```

Streamer registration page:

```text
http://127.0.0.1:8000/register?lang=ru
```

Registration writes streamers to `EBS_DATABASE_PATH` and returns a private
Companion Token once. The EBS stores only the token hash. In production,
`EBS_PUBLIC_URL` is the public site URL and `EBS_API_URL` is the API origin.
Configure `EBS_SMTP_HOST` and `EBS_SMTP_FROM` to also send the Twitch Nick and
Companion Token to the streamer's email address.
If the server provider blocks SMTP ports, set `EBS_MAIL_PROVIDER=yandex_postbox`
and configure Yandex Cloud Postbox HTTPS credentials instead.

Local viewer with EBS polling:

```text
http://127.0.0.1:5173/viewer.html?ebs=http://127.0.0.1:8000&channel=dev-channel
```

Local browser Companion:

```text
http://127.0.0.1:5173/companion.html
```

Docs:

- [Architecture](docs/architecture.md)
- [Local Development](docs/local-dev.md)
- [Companion](docs/companion.md)
- [Twitch Console Setup](docs/twitch-console-setup.md)
- [Twitch EBS Notes](docs/twitch-ebs-notes.md)
- [Finland Deployment](docs/deploy-finland.md)
