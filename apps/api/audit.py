import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def record_audit(
    db: Session,
    *,
    action: str,
    actor: str,
    entity_type: str,
    entity_id: str | None,
    payload: dict[str, Any],
) -> None:
    db.execute(
        text(
            """
        INSERT INTO audit_log(actor, action, entity_type, entity_id, payload)
        VALUES (:actor, :action, :entity_type, :entity_id, CAST(:payload AS jsonb))
        """
        ),
        {
            "actor": actor,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": json.dumps(payload),
        },
    )
