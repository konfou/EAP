import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

from apps.api import crud


def test_insert_event_raw_operational_error(monkeypatch, db_session):
    payload = {
        "event_id": str(uuid4()),
        "ts_event": datetime.now(timezone.utc),
        "event_type": "transaction_completed",
        "source_system": "payments",
    }

    def boom(*_args, **_kwargs):
        raise OperationalError("stmt", {}, Exception("down"))

    monkeypatch.setattr(db_session, "execute", boom)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    ok, reason = crud.insert_event_raw(db_session, payload)
    assert ok is False
    assert reason == "db_insert_error"


def test_quarantine_operational_error(monkeypatch, db_session):
    def boom(*_args, **_kwargs):
        raise OperationalError("stmt", {}, Exception("down"))

    monkeypatch.setattr(db_session, "execute", boom)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    with pytest.raises(OperationalError):
        crud.quarantine(db_session, "bad", {"x": 1})
