import os
from datetime import date, datetime, timezone

from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/risk"),
)

from jobs.dq import job as dq_job


def test_dq_job_writes_summary(db_session):
    report_date = date(2026, 1, 13)
    db_session.execute(
        text(
            """
        INSERT INTO events_raw(event_id, ts_event, event_type, source_system, user_id, value)
        VALUES
          ('11111111-1111-1111-1111-111111111111', :ts, 'transaction_completed', 'payments', 'u1', 10.0),
          ('22222222-2222-2222-2222-222222222222', :ts, 'transaction_completed', 'payments', 'u2', 12.0)
        """
        ),
        {"ts": datetime(2026, 1, 13, 12, 0, tzinfo=timezone.utc)},
    )
    db_session.execute(
        text(
            """
        INSERT INTO events_quarantine(ts_ingested, reason, raw_payload)
        VALUES (:ts, 'schema_violation', '{}'::jsonb)
        """
        ),
        {"ts": datetime(2026, 1, 13, 12, 5, tzinfo=timezone.utc)},
    )
    db_session.commit()

    dq_job.run(report_date)

    row = (
        db_session.execute(
            text("""
            SELECT summary, pass FROM dq_reports WHERE report_date = :d
            """),
            {"d": report_date},
        )
        .mappings()
        .first()
    )
    assert row is not None
    summary = row["summary"]
    assert summary["n_events"] == 2
    assert summary["quarantine_total"] == 1
    assert summary["malformed_events"] == 1
    assert "confidence" in summary
    assert row["pass"] is False
