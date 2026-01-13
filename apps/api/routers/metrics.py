from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db import get_db
from ..schemas import MetricPoint

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/daily", response_model=list[MetricPoint])
def get_metrics_daily(
    metric: str = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    db: Session = Depends(get_db),
) -> list[MetricPoint]:
    rows = (
        db.execute(
            text("""
        SELECT metric_date::text, metric_name, value, dimensions
        FROM metrics_daily
        WHERE metric_name = :metric
          AND metric_date >= CAST(:date_from AS date)
          AND metric_date <= CAST(:date_to AS date)
        ORDER BY metric_date ASC
        """),
            {"metric": metric, "date_from": date_from, "date_to": date_to},
        )
        .mappings()
        .all()
    )

    return [
        MetricPoint(
            metric_date=r["metric_date"],
            metric_name=r["metric_name"],
            value=float(r["value"]),
            dimensions=r["dimensions"],
        )
        for r in rows
    ]
