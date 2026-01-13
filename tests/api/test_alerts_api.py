from datetime import date

from sqlalchemy import text


def test_recent_alerts_endpoint(client, db_session):
    db_session.execute(
        text(
            """
        INSERT INTO alerts(metric_name, metric_date, severity, risk_score, message, context)
        VALUES ('tx_fail_rate', :d, 'WARN', 5.0, 'test', '{}'::jsonb)
        """
        ),
        {"d": date(2026, 1, 13)},
    )
    db_session.commit()

    response = client.get("/alerts/recent")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["metric_name"] == "tx_fail_rate"
    assert data[0]["rule_version"] == "v1"
