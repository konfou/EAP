from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db import get_db
from ..schemas import AlertAction, AlertOut
from ..auth import require_role

router = APIRouter(prefix="/alerts", tags=["alerts"])

ALERT_SELECT = """
    SELECT alert_id, ts::text, metric_name, metric_date::text, severity, rule_version,
           risk_score, message, context, status, acked_by, acked_at::text,
           resolved_by, resolved_at::text
    FROM alerts
"""


@router.get("/recent", response_model=list[AlertOut])
def recent_alerts(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    rows = (
        db.execute(
            text(
                ALERT_SELECT
                + """
        ORDER BY ts DESC
        LIMIT :limit
        """
            ),
            {"limit": limit},
        )
        .mappings()
        .all()
    )
    return [AlertOut(**r) for r in rows]


@router.post("/{alert_id}/ack", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    action: AlertAction,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("operator")),
) -> AlertOut:
    row = (
        db.execute(
            text(
                """
        UPDATE alerts
        SET status = 'ACK',
            acked_by = :actor,
            acked_at = COALESCE(acked_at, NOW())
        WHERE alert_id = :alert_id
        RETURNING alert_id, ts::text, metric_name, metric_date::text, severity, rule_version,
                  risk_score, message, context, status, acked_by, acked_at::text,
                  resolved_by, resolved_at::text
        """
            ),
            {"actor": action.actor, "alert_id": alert_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    db.commit()
    return AlertOut(**row)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: int,
    action: AlertAction,
    db: Session = Depends(get_db),
    _: str = Depends(require_role("operator")),
) -> AlertOut:
    row = (
        db.execute(
            text(
                """
        UPDATE alerts
        SET status = 'RESOLVED',
            resolved_by = :actor,
            resolved_at = COALESCE(resolved_at, NOW()),
            acked_by = COALESCE(acked_by, :actor),
            acked_at = COALESCE(acked_at, NOW())
        WHERE alert_id = :alert_id
        RETURNING alert_id, ts::text, metric_name, metric_date::text, severity, rule_version,
                  risk_score, message, context, status, acked_by, acked_at::text,
                  resolved_by, resolved_at::text
        """
            ),
            {"actor": action.actor, "alert_id": alert_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )
    db.commit()
    return AlertOut(**row)
