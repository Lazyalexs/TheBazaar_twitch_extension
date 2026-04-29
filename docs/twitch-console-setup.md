# Twitch Developer Console Setup

Use this checklist to create the first Local Test version of the extension.

Console:

```text
https://dev.twitch.tv/console/extensions
```

## Create Extension

Recommended first values:

```text
Name: The Bazaar Live Board
Summary: Live board state for The Bazaar streams.
Description: Shows a streamer's current The Bazaar board to viewers using a broadcaster-side Companion and an Extension Backend Service.
Category: Game Extension
Game Category: The Bazaar
Author Name: Lazyalexs
```

The name and public copy can be changed later before review.

## Version Details

Start with:

```text
Version: 0.0.1
```

Keep the frontend JavaScript human-readable for review.

## Capabilities

Recommended for the first EBS test:

```text
Request Identity Link: No
Chat Capabilities: No
Bits: No
Configuration: Extension Configuration Service
Allowlist for URL Fetching Domains:
  http://127.0.0.1:8000
```

Later, after DNS and HTTPS are ready, add the production EBS origin:

```text
https://api.<your-domain>
```

## Asset Hosting

For Local Test, run:

```powershell
.\tools\dev.ps1
```

Set:

```text
Testing Base URI: http://127.0.0.1:5173/
Type of Extension: Video - Fullscreen
Video - Fullscreen View Path: viewer.html
Config Path: config.html
Live Config Path: live.html
```

The Testing Base URI must end with `/`.

Optional later:

```text
Type of Extension: Video - Component
Video - Component View Path: viewer.html
```

Panel mode is not the first target.

## Required Values For `.env`

After creating the extension, copy these values into local `.env`:

```text
TWITCH_EXTENSION_CLIENT_ID=<extension client id>
TWITCH_EXTENSION_OWNER_ID=<owner Twitch user id>
TWITCH_EXTENSION_SECRET_BASE64=<extension secret from console>
TWITCH_EXTENSION_VERSION=0.0.1
```

Use dry-run while checking local Companion ingestion:

```text
EBS_DRY_RUN=1
```

Switch to real Twitch PubSub only after the values are filled:

```text
EBS_DRY_RUN=0
```

Do not commit `.env`.

## First PubSub Test

1. Start the local servers:

   ```powershell
   .\tools\dev.ps1
   ```

2. Set `EBS_DRY_RUN=0` in `.env` and restart EBS.

3. Install and activate the extension on the test broadcaster channel.

4. Open the broadcaster Live Config view.

5. Send fake state:

   ```powershell
   .\.venv\Scripts\python companion\fake_companion.py --once
   ```

6. Open the channel as a viewer and confirm `viewer.html` receives the broadcast.

## Official References

- Local Test: https://dev.twitch.tv/docs/tutorials/extension-101-tutorial-series/local-test/
- Life Cycle Management: https://dev.twitch.tv/docs/extensions/releasing-and-maintaining/
- Extensions Reference: https://dev.twitch.tv/docs/extensions/reference/
- Send Extension PubSub Message: https://dev.twitch.tv/docs/api/reference/#send-extension-pubsub-message

