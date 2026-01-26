from apps.dashboard import layout as dashboard_layout


def test_build_layout(monkeypatch):
    monkeypatch.setattr(
        dashboard_layout,
        "fetch_overview",
        lambda _: {
            "health_score": 90,
            "stability_index": 95,
            "dq_confidence": 88,
            "financial_exposure": 0,
            "top_risks": [],
        },
    )
    monkeypatch.setattr(
        dashboard_layout,
        "fetch_advanced_data",
        lambda *_: {
            "metrics_table": [],
            "alerts_table": [],
            "notifications_table": [],
            "anomalies_table": [],
            "telemetry_table": [],
            "readiness_ok": True,
            "data_source": "api",
        },
    )

    layout = dashboard_layout.build_layout()
    assert layout is not None
    assert "Executive Risk Dashboard" in str(layout)
