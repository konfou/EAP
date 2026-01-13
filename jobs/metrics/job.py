"""Deterministic KPI calculations for daily business metrics."""

import json
import os
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from eap.logging import configure_logging

DB = os.environ["DATABASE_URL"]
engine = create_engine(DB, pool_pre_ping=True)
logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))


def upsert_metric(
    conn, metric_date: date, name: str, value: float, dimensions: dict
) -> None:
    """Idempotently persist a daily metric."""
    conn.execute(
        text(
            """
      INSERT INTO metrics_daily(metric_date, metric_name, value, dimensions)
      VALUES (CAST(:d AS date), :name, :value, CAST(:dim AS jsonb))
      ON CONFLICT (metric_date, metric_name, dimensions) DO UPDATE
        SET value = EXCLUDED.value,
            computed_at = NOW()
    """
        ),
        {
            "d": metric_date,
            "name": name,
            "value": float(value),
            "dim": json.dumps(dimensions),
        },
    )


def fetch_dau(conn, metric_date: date) -> float:
    """Daily active users (unique user_id)."""
    return (
        conn.execute(
            text(
                """
        SELECT COUNT(DISTINCT user_id) AS dau
        FROM events_raw
        WHERE user_id IS NOT NULL
          AND ts_event >= CAST(:d AS date) AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """
            ),
            {"d": metric_date},
        ).scalar()
        or 0
    )


def fetch_tx_completed(conn, metric_date: date) -> tuple[float, float]:
    """Count and sum value for completed transactions."""
    row = (
        conn.execute(
            text(
                """
        SELECT COUNT(*) AS n, COALESCE(SUM(value),0) AS total_value
        FROM events_raw
        WHERE event_type='transaction_completed'
          AND ts_event >= CAST(:d AS date) AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """
            ),
            {"d": metric_date},
        )
        .mappings()
        .first()
    )
    return float(row["n"]), float(row["total_value"])


def fetch_tx_fail_rate(conn, metric_date: date) -> float:
    """Failure rate for transaction events."""
    row = (
        conn.execute(
            text(
                """
        SELECT
          SUM(CASE WHEN event_type='transaction_failed' THEN 1 ELSE 0 END) AS failed,
          SUM(CASE WHEN event_type IN ('transaction_failed','transaction_completed') THEN 1 ELSE 0 END) AS denom
        FROM events_raw
        WHERE ts_event >= CAST(:d AS date) AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """
            ),
            {"d": metric_date},
        )
        .mappings()
        .first()
    )
    denom = float(row["denom"] or 0)
    return float(row["failed"] or 0) / denom if denom else 0.0


def fetch_latency_p95(conn, metric_date: date) -> float | None:
    """p95 latency for system_latency events."""
    return conn.execute(
        text(
            """
      SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) AS p95
      FROM events_raw
      WHERE event_type='system_latency'
        AND value IS NOT NULL
        AND ts_event >= CAST(:d AS date) AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """
        ),
        {"d": metric_date},
    ).scalar()


def backfill(start_date: date, end_date: date) -> None:
    """Backfill metrics over an inclusive date range."""
    if start_date > end_date:
        raise ValueError("start_date must be before end_date")
    logger.info(
        "metrics_backfill_start",
        start_date=str(start_date),
        end_date=str(end_date),
    )
    current = start_date
    while current <= end_date:
        run(current)
        current += timedelta(days=1)
    logger.info(
        "metrics_backfill_complete",
        start_date=str(start_date),
        end_date=str(end_date),
    )


def run(metric_date: date | None = None) -> None:
    """Compute and persist daily KPIs."""
    if metric_date is None:
        metric_date = date.today() - timedelta(days=1)
    logger.info("metrics_run_start", metric_date=str(metric_date))

    with engine.begin() as conn:
        dau = fetch_dau(conn, metric_date)
        upsert_metric(conn, metric_date, "dau", float(dau), {})

        tx_count, tx_value = fetch_tx_completed(conn, metric_date)
        upsert_metric(conn, metric_date, "tx_completed_count", tx_count, {})
        upsert_metric(conn, metric_date, "tx_completed_value", tx_value, {})

        fail_rate = fetch_tx_fail_rate(conn, metric_date)
        upsert_metric(conn, metric_date, "tx_fail_rate", fail_rate, {})

        p95 = fetch_latency_p95(conn, metric_date)
        if p95 is not None:
            upsert_metric(conn, metric_date, "latency_p95_ms", float(p95), {})
    logger.info("metrics_run_complete", metric_date=str(metric_date))
