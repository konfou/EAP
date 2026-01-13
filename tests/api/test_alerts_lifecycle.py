from datetime import date

from sqlalchemy import text


def test_alert_ack_and_resolve(client, db_session):
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

    alert_id = db_session.execute(text("SELECT alert_id FROM alerts")).scalar()

    response = client.post(
        f"/alerts/{alert_id}/ack",
        json={"actor": "ops-user"},
        headers={"X-Role": "operator"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ACK"
    assert response.json()["acked_by"] == "ops-user"

    response = client.post(
        f"/alerts/{alert_id}/resolve",
        json={"actor": "ops-user"},
        headers={"X-Role": "operator"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"
    assert response.json()["resolved_by"] == "ops-user"
