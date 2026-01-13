import os
from datetime import date, timedelta

from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/risk"),
)

from jobs.anomaly import job as anomaly_job


def test_anomaly_job_inserts_alerts(db_session):
    target_date = date(2026, 1, 13)
    baseline_vals = [0.01, 0.02, 0.015, 0.012, 0.018, 0.011, 0.019]
    for index, value in enumerate(baseline_vals, start=1):
        day = target_date - timedelta(days=8 - index)
        db_session.execute(
            text(
                """
            INSERT INTO metrics_daily(metric_date, metric_name, value, dimensions)
            VALUES (:d, 'tx_fail_rate', :v, '{}'::jsonb)
            """
            ),
            {"d": day, "v": value},
        )
    db_session.execute(
        text(
            """
        INSERT INTO metrics_daily(metric_date, metric_name, value, dimensions)
        VALUES (:d, 'tx_fail_rate', :v, '{}'::jsonb)
        """
        ),
        {"d": target_date, "v": 0.2},
    )
    db_session.commit()

    anomaly_job.run(target_date)

    rows = (
        db_session.execute(
            text(
                """
            SELECT context->>'method' AS method
            FROM alerts
            WHERE metric_name = 'tx_fail_rate' AND metric_date = :d
            """
            ),
            {"d": target_date},
        )
        .mappings()
        .all()
    )
    methods = {row["method"] for row in rows}
    assert "z_score" in methods
