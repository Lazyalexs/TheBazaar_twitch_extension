from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def compact_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def read_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Board file must contain a JSON object")
    return data


def build_snapshot(seq: int, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": 1,
        "type": "snapshot",
        "seq": seq,
        "sentAt": int(time.time() * 1000),
        "patch": str(payload.pop("patch", "bazaar-live")),
        "runId": run_id,
        "payload": payload,
    }


def post_snapshot(base_url: str, channel_id: str, token: str, snapshot: dict[str, Any]):
    url = f"{base_url.rstrip('/')}/v1/companion/{channel_id}/snapshot"
    request = urllib.request.Request(
        url,
        data=compact_json(snapshot),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "TheBazaarFileCompanion/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"{response.status} {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"{exc.code} {body}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish a board JSON file as The Bazaar Twitch EBS snapshots."
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--url", default=os.environ.get("EBS_PUBLIC_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--channel", default=os.environ.get("COMPANION_CHANNEL_ID", "dev-channel"))
    parser.add_argument(
        "--token",
        default=os.environ.get("COMPANION_SHARED_TOKEN", "dev-companion-token"),
    )
    parser.add_argument("--interval", type=float, default=1.1)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    seq = 1
    run_id = f"file-companion-{int(time.time())}"
    last_mtime: float | None = None

    while True:
        stat = args.file.stat()
        if args.once or stat.st_mtime != last_mtime:
            payload = read_payload(args.file)
            post_snapshot(
                args.url,
                args.channel,
                args.token,
                build_snapshot(seq, run_id, payload),
            )
            seq += 1
            last_mtime = stat.st_mtime

        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
