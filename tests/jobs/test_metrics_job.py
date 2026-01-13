import os
from datetime import date, datetime, timezone

from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/risk"),
)

from jobs.metrics import job as batch_metrics_job


def test_batch_metrics_job_computes_kpis(db_session):
    metric_date = date(2026, 1, 13)
    ts = datetime(2026, 1, 13, 9, 0, tzinfo=timezone.utc)
    db_session.execute(
        text(
            """
        INSERT INTO events_raw(event_id, ts_event, event_type, source_system, user_id, value)
        VALUES
          ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', :ts, 'transaction_completed', 'payments', 'u1', 100.0),
          ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', :ts, 'transaction_completed', 'payments', 'u2', 50.0),
          ('cccccccc-cccc-cccc-cccc-cccccccccccc', :ts, 'transaction_failed', 'payments', 'u3', 0.0),
          ('dddddddd-dddd-dddd-dddd-dddddddddddd', :ts, 'system_latency', 'core', 'u4', 250.0)
        """
        ),
        {"ts": ts},
    )
    db_session.commit()

    batch_metrics_job.run(metric_date)

    rows = (
        db_session.execute(
            text(
                """
            SELECT metric_name, value FROM metrics_daily
            WHERE metric_date = :d
            """
            ),
            {"d": metric_date},
        )
        .mappings()
        .all()
    )
    metrics = {row["metric_name"]: float(row["value"]) for row in rows}
    assert metrics["dau"] == 4.0
    assert metrics["tx_completed_count"] == 2.0
    assert metrics["tx_completed_value"] == 150.0
    assert metrics["tx_fail_rate"] == 1.0 / 3.0
    assert metrics["latency_p95_ms"] == 250.0


def test_batch_metrics_backfill(db_session):
    first_date = date(2026, 1, 12)
    second_date = date(2026, 1, 13)
    db_session.execute(
        text(
            """
        INSERT INTO events_raw(event_id, ts_event, event_type, source_system, user_id, value)
        VALUES
          ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', :ts1, 'transaction_completed', 'payments', 'u1', 10.0),
          ('ffffffff-ffff-ffff-ffff-ffffffffffff', :ts2, 'transaction_completed', 'payments', 'u2', 20.0)
        """
        ),
        {
            "ts1": datetime(2026, 1, 12, 10, 0, tzinfo=timezone.utc),
            "ts2": datetime(2026, 1, 13, 10, 0, tzinfo=timezone.utc),
        },
    )
    db_session.commit()

    batch_metrics_job.backfill(first_date, second_date)

    rows = (
        db_session.execute(
            text(
                """
            SELECT metric_date, metric_name, value
            FROM metrics_daily
            WHERE metric_name = 'tx_completed_count'
            ORDER BY metric_date ASC
            """
            )
        )
        .mappings()
        .all()
    )
    results = {row["metric_date"]: float(row["value"]) for row in rows}
    assert results[first_date] == 1.0
    assert results[second_date] == 1.0
