from datetime import date

from apps.dashboard import app as dashboard_app


def test_update_advanced_panel(monkeypatch):
    def fake_fetch_advanced_data(start, end):
        return {
            "metrics_table": [{"Metric": "dau", "Value": 10}],
            "alerts_table": [],
            "notifications_table": [],
            "anomalies_table": [],
            "telemetry_table": [{"Metric": "total_requests", "Value": 1}],
            "readiness_ok": True,
            "data_source": "api",
            "dq_summary_text": "2026-01-13 | pass=True | confidence=0.5",
        }

    monkeypatch.setattr(
        dashboard_app,
        "fetch_advanced_data",
        fake_fetch_advanced_data,
    )

    results = dashboard_app.update_advanced_panel(
        0, date(2026, 1, 13).isoformat(), date(2026, 1, 13).isoformat()
    )
    assert results[1][0]["Metric"] == "dau"
    assert results[4][0]["Metric"] == "total_requests"
