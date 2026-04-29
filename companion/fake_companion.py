from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


def build_snapshot(seq: int, run_id: str) -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    cooldown = max(0.0, round(6.0 - (seq % 6), 1))
    gold = 10 + seq
    return {
        "v": 1,
        "type": "snapshot",
        "seq": seq,
        "sentAt": now_ms,
        "patch": "13.3-dev",
        "runId": run_id,
        "payload": {
            "debugHotspots": True,
            "hero": "vanessa",
            "day": 7,
            "gold": gold,
            "health": 82,
            "maxHealth": 100,
            "phase": "combat" if seq % 2 else "shopping",
            "board": [
                {
                    "slot": 0,
                    "id": "dishwasher",
                    "tier": "gold",
                    "enchants": [],
                    "cd": cooldown,
                    "ammo": None,
                    "bbox": {"x": 0.18, "y": 0.55, "w": 0.1, "h": 0.18},
                },
                {
                    "slot": 1,
                    "id": "small_cutlass",
                    "tier": "silver",
                    "enchants": ["burn"],
                    "cd": 4.5,
                    "ammo": None,
                    "bbox": {"x": 0.31, "y": 0.55, "w": 0.1, "h": 0.18},
                },
            ],
            "stash": [{"id": "spare_rigging", "tier": "bronze"}],
            "skills": [{"id": "sea_legs", "tier": "bronze"}],
        },
    }


def post_snapshot(base_url: str, channel_id: str, token: str, snapshot: dict[str, Any]):
    url = f"{base_url.rstrip('/')}/v1/companion/{channel_id}/snapshot"
    raw = json.dumps(snapshot, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "TheBazaarFakeCompanion/0.1",
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--channel", default="dev-channel")
    parser.add_argument("--token", default="dev-companion-token")
    parser.add_argument("--interval", type=float, default=1.1)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    seq = 1
    run_id = f"fake-local-run-{int(time.time())}"
    while True:
        post_snapshot(args.url, args.channel, args.token, build_snapshot(seq, run_id))
        if args.once:
            return
        seq += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
