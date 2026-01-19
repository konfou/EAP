from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from typing import Dict
from ..db import get_db
from ..schemas import IngestRequest, IngestResponse
from ..crud import insert_event_raw, quarantine
from ..audit import record_audit
from ..auth import require_role

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/events", response_model=IngestResponse)
def ingest_events(
    req: IngestRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("operator")),
    actor: str = Header(default="system", alias="X-Actor"),
) -> IngestResponse:
    accepted = 0
    rejected = 0
    reasons: Dict[str, int] = {}

    for event in req.events:
        event_db = event.model_dump()
        event_json = event.model_dump(mode="json")
        with db.begin_nested():
            ok, reason = insert_event_raw(db, event_db)
        if ok:
            accepted += 1
        else:
            rejected += 1
            reasons[reason] = reasons.get(reason, 0) + 1
            with db.begin_nested():
                quarantine(db, reason=reason, payload=event_json)

    record_audit(
        db,
        action="ingest_events",
        actor=actor,
        entity_type="events_batch",
        entity_id=None,
        payload={
            "accepted": accepted,
            "rejected": rejected,
            "rejected_reasons": reasons,
        },
    )
    db.commit()
    return IngestResponse(
        accepted=accepted, rejected=rejected, rejected_reasons=reasons
    )
