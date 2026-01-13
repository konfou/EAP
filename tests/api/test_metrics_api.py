from sqlalchemy import text
from datetime import date


def test_metrics_daily_endpoint(client, db_session):
    db_session.execute(
        text("""
        INSERT INTO metrics_daily(metric_date, metric_name, value, dimensions)
        VALUES (:d, :m, :v, '{}'::jsonb)
        """),
        {"d": date(2026, 1, 13), "m": "dau", "v": 10.0},
    )
    db_session.commit()

    r = client.get(
        "/metrics/daily",
        params={
            "metric": "dau",
            "date_from": "2026-01-13",
            "date_to": "2026-01-13",
        },
    )

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["value"] == 10.0
