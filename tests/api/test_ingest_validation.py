import uuid
from datetime import datetime, timezone


def test_valid_event_ingestion(client):
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "ts_event": datetime.now(timezone.utc).isoformat(),
                "event_type": "transaction_completed",
                "source_system": "payments",
                "user_id": "u123",
                "value": 50.0,
                "measurement_uncertainty": 0.2,
                "properties": {"currency": "EUR"},
            }
        ]
    }

    r = client.post("/ingest/events", json=payload, headers={"X-Role": "operator"})
    assert r.status_code == 200

    data = r.json()
    assert data["accepted"] == 1
    assert data["rejected"] == 0


def test_invalid_event_type_is_rejected(client):
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "ts_event": "2026-01-13T00:00:00Z",
                "event_type": "unknown_event",
                "source_system": "payments",
            }
        ]
    }

    r = client.post("/ingest/events", json=payload, headers={"X-Role": "operator"})
    assert r.status_code == 422  # FastAPI validation error
