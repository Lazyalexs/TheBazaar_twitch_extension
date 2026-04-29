from fastapi.testclient import TestClient

from ebs.app.main import app


client = TestClient(app)


def _snapshot(seq: int = 1):
    return {
        "v": 1,
        "type": "snapshot",
        "seq": seq,
        "sentAt": 1770000000000,
        "patch": "13.3-dev",
        "runId": "test-run",
        "payload": {
            "hero": "vanessa",
            "day": 7,
            "gold": 14,
            "health": 82,
            "maxHealth": 100,
            "phase": "combat",
            "board": [
                {
                    "slot": 0,
                    "id": "dishwasher",
                    "tier": "gold",
                    "enchants": [],
                    "cd": 3.2,
                    "bbox": {"x": 0.1, "y": 0.2, "w": 0.08, "h": 0.12},
                }
            ],
            "stash": [],
            "skills": [],
        },
    }


def test_health_exposes_dry_run_defaults():
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["dryRun"] is True
    assert "dev-channel" in body["configuredChannels"]


def test_companion_ingest_requires_token():
    response = client.post("/v1/companion/dev-channel/snapshot", json=_snapshot())

    assert response.status_code == 401
    assert response.json()["detail"]["error"] == "invalid_companion_token"


def test_companion_ingest_stores_latest_snapshot():
    response = client.post(
        "/v1/companion/dev-channel/snapshot",
        headers={"Authorization": "Bearer dev-companion-token"},
        json=_snapshot(seq=101),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dryRun"] is True
    assert body["sentToTwitch"] is False
    assert body["seq"] == 101
    assert body["sizeBytes"] < 5000

    latest = client.get("/v1/channels/dev-channel/latest")
    assert latest.status_code == 200
    latest_body = latest.json()
    assert latest_body["message"]["seq"] == 101
    assert latest_body["message"]["payload"]["hero"] == "vanessa"
