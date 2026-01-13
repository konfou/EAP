"""In-memory request telemetry for basic observability."""

from dataclasses import dataclass
from threading import Lock

from sqlalchemy import text

from .db import engine


@dataclass
class TelemetrySnapshot:
    total_requests: int
    total_errors: int
    avg_latency_ms: float


_lock = Lock()
_total_requests = 0
_total_errors = 0
_total_latency_ms = 0.0


def record_request(status_code: int, latency_ms: float) -> None:
    global _total_requests, _total_errors, _total_latency_ms
    with _lock:
        _total_requests += 1
        if status_code >= 500:
            _total_errors += 1
        _total_latency_ms += latency_ms

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO api_metrics(id, total_requests, total_errors, total_latency_ms)
                VALUES (1, :requests, :errors, :latency)
                ON CONFLICT (id) DO UPDATE
                  SET total_requests = api_metrics.total_requests + :requests,
                      total_errors = api_metrics.total_errors + :errors,
                      total_latency_ms = api_metrics.total_latency_ms + :latency,
                      updated_at = NOW()
                """
                ),
                {
                    "requests": 1,
                    "errors": 1 if status_code >= 500 else 0,
                    "latency": latency_ms,
                },
            )
    except Exception:
        pass


def snapshot() -> TelemetrySnapshot:
    total_requests = 0
    total_errors = 0
    total_latency_ms = 0.0

    try:
        with engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        """
                    SELECT total_requests, total_errors, total_latency_ms
                    FROM api_metrics
                    WHERE id = 1
                    """
                    )
                )
                .mappings()
                .first()
            )
        if row:
            total_requests = int(row["total_requests"])
            total_errors = int(row["total_errors"])
            total_latency_ms = float(row["total_latency_ms"])
    except Exception:
        with _lock:
            total_requests = _total_requests
            total_errors = _total_errors
            total_latency_ms = _total_latency_ms

    avg_latency = total_latency_ms / total_requests if total_requests else 0.0
    return TelemetrySnapshot(
        total_requests=total_requests,
        total_errors=total_errors,
        avg_latency_ms=avg_latency,
    )
