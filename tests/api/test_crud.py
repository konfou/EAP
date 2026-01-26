from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from apps.api.crud import insert_event_raw


def test_insert_event_raw_success(db_session):
    payload = {
        "event_id": str(uuid4()),
        "ts_event": datetime.now(timezone.utc),
        "event_type": "transaction_completed",
        "source_system": "payments",
        "value": 12.5,
    }
    ok, reason = insert_event_raw(db_session, payload)
    assert ok is True
    assert reason == "ok"
    db_session.commit()

    stored = db_session.execute(
        text("SELECT COUNT(*) FROM events_raw WHERE event_id = :eid"),
        {"eid": payload["event_id"]},
    ).scalar()
    assert stored == 1


def test_insert_event_raw_duplicate(db_session):
    event_id = str(uuid4())
    payload = {
        "event_id": event_id,
        "ts_event": datetime.now(timezone.utc),
        "event_type": "transaction_completed",
        "source_system": "payments",
    }
    insert_event_raw(db_session, payload)
    db_session.commit()

    ok, reason = insert_event_raw(db_session, payload)
    assert ok is False
    assert reason == "duplicate_event_id"


def test_insert_event_raw_missing_table(db_session):
    db_session.execute(text("DROP TABLE events_raw"))
    ok, reason = insert_event_raw(
        db_session,
        {
            "event_id": str(uuid4()),
            "ts_event": datetime.now(timezone.utc),
            "event_type": "transaction_completed",
            "source_system": "payments",
        },
    )
    assert ok is False
    assert reason == "db_insert_error"
