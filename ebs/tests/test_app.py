from fastapi.testclient import TestClient
from types import SimpleNamespace

from ebs.app.database import TokenStore
from ebs.app.main import app
from ebs.app import main as main_module


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


def test_landing_and_registration_are_separate_pages():
    landing = client.get("/new?lang=ru")
    registration = client.get("/register?lang=ru")
    landing_head = client.head("/new?lang=ru")
    registration_head = client.head("/register?lang=ru")

    assert landing.status_code == 200
    assert registration.status_code == 200
    assert landing_head.status_code == 200
    assert registration_head.status_code == 200
    assert "Зарегистрироваться" in landing.text
    assert 'id="register-form"' not in landing.text
    assert 'id="register-form"' in registration.text
    assert "Twitch Nick" in registration.text
    assert 'name="inviteCode"' not in registration.text
    assert "const apiBaseUrl" in registration.text
    assert "${apiBaseUrl}/api/register" in registration.text
    assert '<meta name="description"' in landing.text
    assert '<link rel="canonical" href="http://127.0.0.1:8000/new?lang=ru">' in landing.text
    assert '<meta property="og:title" content="The Bazaar Live Board">' in landing.text
    assert '<meta name="description"' in registration.text
    assert (
        '<link rel="canonical" href="http://127.0.0.1:8000/register?lang=ru">'
        in registration.text
    )
    assert '<meta property="og:type" content="website">' in registration.text


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


def test_registration_token_can_publish_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(
        main_module,
        "token_store",
        TokenStore(tmp_path / "tokens.sqlite3"),
    )
    monkeypatch.setattr(
        main_module.identity_resolver,
        "resolve_login",
        lambda login: SimpleNamespace(
            channel_id="123456789",
            login=str(login).lower(),
            display_name="Test Streamer",
        ),
    )

    registration = client.post(
        "/api/register",
        json={
            "channelLogin": "TestStreamer",
            "email": "streamer@example.com",
            "language": "en",
        },
    )

    assert registration.status_code == 200
    credentials = registration.json()
    assert credentials["channelId"] == "123456789"
    assert credentials["channelLogin"] == "teststreamer"
    assert credentials["email"] == "streamer@example.com"
    assert credentials["companionToken"]
    assert credentials["emailSent"] is False

    verify = client.post(
        "/api/companion/verify",
        json={
            "channelLogin": "teststreamer",
            "token": credentials["companionToken"],
        },
    )
    assert verify.status_code == 200
    assert verify.json()["displayName"] == "Test Streamer"
    assert verify.json()["channelId"] == "123456789"

    snapshot = client.post(
        "/v1/companion/teststreamer/snapshot",
        headers={"Authorization": f"Bearer {credentials['companionToken']}"},
        json=_snapshot(seq=202),
    )
    assert snapshot.status_code == 200
    assert snapshot.json()["seq"] == 202
    assert snapshot.json()["channelId"] == "123456789"
