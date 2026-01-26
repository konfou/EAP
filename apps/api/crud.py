import time

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from typing import Any, Dict, Tuple


def insert_event_raw(db: Session, e: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Returns (accepted, reason_if_rejected)
    """
    payload = {
        "user_id": None,
        "value": None,
        "measurement_uncertainty": None,
        **e,
    }
    payload["properties"] = __import__("json").dumps(e.get("properties", {}))
    for attempt in range(3):
        try:
            db.execute(
                text("""
                INSERT INTO events_raw(event_id, ts_event, event_type, source_system, user_id, value, measurement_uncertainty, properties)
                VALUES (:event_id, :ts_event, :event_type, :source_system, :user_id, :value, :measurement_uncertainty, CAST(:properties AS jsonb))
                """),
                payload,
            )
            return True, "ok"
        except OperationalError:
            db.rollback()
            if attempt == 2:
                return False, "db_insert_error"
            time.sleep(0.2 * (attempt + 1))
        except Exception as ex:
            db.rollback()
            msg = str(ex).lower()
            if "duplicate key value" in msg or "unique constraint" in msg:
                return False, "duplicate_event_id"
            return False, "db_insert_error"
    return False, "db_insert_error"


def quarantine(db: Session, reason: str, payload: Dict[str, Any]) -> None:
    safe_payload = jsonable_encoder(payload)
    try:
        data = {"reason": reason, "payload": __import__("json").dumps(safe_payload)}
        for attempt in range(3):
            try:
                db.execute(
                    text(
                        """INSERT INTO events_quarantine(reason, raw_payload) VALUES (:reason, CAST(:payload AS jsonb))"""
                    ),
                    data,
                )
                break
            except OperationalError:
                db.rollback()
                if attempt == 2:
                    raise
                time.sleep(0.2 * (attempt + 1))
    except Exception:
        db.rollback()
        raise
