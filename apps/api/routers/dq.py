from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..db import get_db
from ..schemas import DQReportOut

router = APIRouter(prefix="/dq", tags=["data-quality"])


@router.get("/latest", response_model=DQReportOut)
def latest_dq(db: Session = Depends(get_db)) -> DQReportOut:
    row = (
        db.execute(
            text(
                """SELECT report_date::text, pass, summary FROM dq_reports ORDER BY report_date DESC LIMIT 1"""
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        payload: dict[str, Any] = {
            "report_date": "1970-01-01",
            "pass": False,
            "summary": {"note": "no reports yet"},
        }
        return DQReportOut.model_validate(payload)
    return DQReportOut.model_validate(row)
