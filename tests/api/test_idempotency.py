import uuid
from datetime import datetime, timezone


def test_duplicate_event_id_is_quarantined(client):
    eid = str(uuid.uuid4())

    payload = {
        "events": [
            {
                "event_id": eid,
                "ts_event": datetime.now(timezone.utc).isoformat(),
                "event_type": "transaction_completed",
                "source_system": "payments",
                "value": 100.0,
            }
        ]
    }

    headers = {"X-Role": "operator"}
    r1 = client.post("/ingest/events", json=payload, headers=headers)
    r2 = client.post("/ingest/events", json=payload, headers=headers)

    assert r1.json()["accepted"] == 1
    assert r2.json()["accepted"] == 0
    assert r2.json()["rejected"] == 1
    assert "duplicate_event_id" in r2.json()["rejected_reasons"]
