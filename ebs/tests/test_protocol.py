from ebs.app.protocol import PubSubEnvelope, compact_size_bytes


def test_snapshot_payload_is_normalized_and_small():
    envelope = PubSubEnvelope.model_validate(
        {
            "v": 1,
            "type": "snapshot",
            "seq": 1,
            "sentAt": 1770000000000,
            "patch": "13.3",
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
                        "source": "game",
                        "confidence": 1,
                        "tier": "gold",
                        "enchants": [],
                        "cd": 3.2,
                        "bbox": {"x": 0.1, "y": 0.2, "w": 0.08, "h": 0.12},
                    }
                ],
            },
        }
    )

    assert envelope.payload["board"][0]["id"] == "dishwasher"
    assert envelope.payload["board"][0]["source"] == "game"
    assert envelope.payload["board"][0]["confidence"] == 1
    assert envelope.payload["board"][0]["bbox"]["x"] == 0.1
    assert compact_size_bytes(envelope.model_dump(exclude_none=True)) < 5000
