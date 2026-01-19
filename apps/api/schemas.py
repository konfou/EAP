from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

ALLOWED_EVENT_TYPES = {
    "transaction_initiated",
    "transaction_completed",
    "transaction_failed",
    "system_latency",
    "user_access",
    "config_change",
}


class EventIn(BaseModel):
    event_id: UUID
    ts_event: datetime
    event_type: str
    source_system: str
    user_id: Optional[str] = None
    value: Optional[float] = None
    measurement_uncertainty: Optional[float] = Field(default=None, ge=0)
    properties: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"event_type must be one of {sorted(ALLOWED_EVENT_TYPES)}")
        return v


class IngestRequest(BaseModel):
    events: List[EventIn]


class IngestResponse(BaseModel):
    accepted: int
    rejected: int
    rejected_reasons: Dict[str, int]  # reason -> count


class MetricPoint(BaseModel):
    metric_date: str
    metric_name: str
    value: float
    dimensions: Dict[str, Any]


class DQReportOut(BaseModel):
    report_date: str
    pass_: bool = Field(alias="pass")
    summary: Dict[str, Any]


class AlertOut(BaseModel):
    alert_id: int
    ts: str
    metric_name: str
    metric_date: Optional[str]
    severity: str
    rule_version: str
    risk_score: float
    message: str
    context: Dict[str, Any]
    status: str
    acked_by: Optional[str] = None
    acked_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None


class AlertAction(BaseModel):
    actor: str


class AlertNotificationOut(BaseModel):
    notification_id: int
    alert_id: int
    channel: str
    target: str
    status: str
    sent_at: Optional[str] = None
    created_at: str
    last_error: Optional[str] = None
    metric_name: Optional[str] = None
    severity: Optional[str] = None
