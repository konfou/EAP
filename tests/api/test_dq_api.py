from datetime import date

from sqlalchemy import text


def test_latest_dq_endpoint(client, db_session):
    db_session.execute(
        text(
            """
        INSERT INTO dq_reports(report_date, pass, summary)
        VALUES (:d, TRUE, '{"note": "ok"}'::jsonb)
        """
        ),
        {"d": date(2026, 1, 13)},
    )
    db_session.commit()

    response = client.get("/dq/latest")
    assert response.status_code == 200
    assert response.json()["report_date"] == "2026-01-13"
