# Local Development

This mode does not require a domain, certificate, or Twitch secrets.

## 1. Prepare Environment

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python -m pip install -r ebs\requirements-dev.txt
```

The default `.env` values keep the EBS in dry-run mode:

```text
EBS_DRY_RUN=1
COMPANION_CHANNEL_ID=dev-channel
COMPANION_SHARED_TOKEN=dev-companion-token
```

## 2. Run EBS

The simplest route is to start both local servers:

```powershell
.\tools\dev.ps1
```

Or run the EBS manually:

```powershell
.\.venv\Scripts\python -m uvicorn ebs.app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/health
```

## 2a. Refresh BazaarDB Data

The checked-in `extension/data/items.min.json` can be refreshed from BazaarDB:

```powershell
node tools\sync-bazaardb-data.mjs
```

This should be done when the game patch changes.

## 3. Send Fake State

In another terminal:

```powershell
.\.venv\Scripts\python companion\fake_companion.py --once
```

Or stream fake updates:

```powershell
.\.venv\Scripts\python companion\fake_companion.py
```

The latest accepted state is available at:

```text
http://127.0.0.1:8000/v1/channels/dev-channel/latest
```

To send a specific board layout, edit `companion/board.sample.json` and run:

```powershell
.\.venv\Scripts\python companion\file_companion.py companion\board.sample.json --once
```

## 4. Preview Viewer

Serve the extension folder:

```powershell
python -m http.server 5173 -d extension
```

Open:

```text
http://127.0.0.1:5173/viewer.html?demo=1
```

To see state coming through the local EBS instead of the static demo snapshot,
open:

```text
http://127.0.0.1:5173/viewer.html?ebs=http://127.0.0.1:8000&channel=dev-channel
```

Then run:

```powershell
.\.venv\Scripts\python companion\fake_companion.py
```

The board should update about once per second.

The local live dashboard is available at:

```text
http://127.0.0.1:5173/live.html
```

The config page is available at:

```text
http://127.0.0.1:5173/config.html
```

Inside Twitch, `live.html` and `config.html` will also receive Twitch Helper
authorization and can use the real channel ID automatically.

## 5. Run Checks

```powershell
.\.venv\Scripts\python -m pytest ebs\tests
```

## 6. Stop Local Servers

```powershell
.\tools\stop-dev.ps1
```
