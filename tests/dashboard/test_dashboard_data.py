import importlib
from datetime import date

from sqlalchemy import text


class FakeResponse:
    def __init__(self, payload: str):
        self.payload = payload

    def read(self):
        return self.payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _reload_data_module(monkeypatch, source: str):
    monkeypatch.setenv("DASHBOARD_DATA_SOURCE", source)
    monkeypatch.setenv("API_BASE_URL", "http://localhost:8000")
    module = importlib.import_module("apps.dashboard.data")
    return importlib.reload(module)


def test_dashboard_sql_mode(monkeypatch, db_session):
    report_date = date(2026, 1, 13)
    db_session.execute(
        text(
            """
        INSERT INTO dq_reports(report_date, pass, summary)
        VALUES (:d, TRUE, '{"confidence": 0.75}'::jsonb)
        """
        ),
        {"d": report_date},
    )
    db_session.execute(
        text(
            """
        INSERT INTO alerts(metric_name, metric_date, severity, risk_score, message, context)
        VALUES ('tx_fail_rate', :d, 'WARN', 12.3, 'spike', '{"impact": 4, "method": "z_score"}'::jsonb)
        """
        ),
        {"d": report_date},
    )
    db_session.execute(
        text(
            """
        INSERT INTO metrics_daily(metric_date, metric_name, value, dimensions)
        VALUES (:d, 'tx_fail_rate', 0.25, '{}'::jsonb)
        """
        ),
        {"d": report_date},
    )
    db_session.commit()

    data_module = _reload_data_module(monkeypatch, "sql")
    monkeypatch.setattr(
        data_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse("http_requests_total 1"),
    )
    monkeypatch.setattr(
        data_module,
        "_fetch_json",
        lambda url: {"ok": True} if url.endswith("/ready") else {"ok": True},
    )

    overview = data_module.fetch_overview(report_date)
    assert overview["top_risks"]
    assert overview["dq_confidence"] == 75.0

    advanced = data_module.fetch_advanced_data(report_date, report_date)
    assert advanced["data_source"] == "sql"
    assert advanced["anomalies_table"][0]["Metric"] == "tx_fail_rate"


def test_dashboard_api_mode(monkeypatch):
    data_module = _reload_data_module(monkeypatch, "api")

    def fake_fetch_json(url):
        if url.endswith("/dq/latest"):
            return {
                "report_date": "2026-01-13",
                "pass": True,
                "summary": {"confidence": 0.5},
            }
        if "/alerts/recent" in url:
            return [
                {
                    "metric_name": "tx_fail_rate",
                    "severity": "WARN",
                    "risk_score": 10,
                    "message": "spike",
                    "status": "OPEN",
                    "context": {"impact": 4, "method": "ewma"},
                    "ts": "2026-01-13T10:00:00Z",
                }
            ]
        if "/metrics/daily" in url:
            return [{"metric_name": "tx_fail_rate", "value": 0.25}]
        if url.endswith("/metrics"):
            return {"total_requests": 5, "total_errors": 0, "avg_latency_ms": 3.5}
        if url.endswith("/ready") or url.endswith("/health"):
            return {"ok": True}
        return None

    monkeypatch.setattr(
        data_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse("http_requests_total 1"),
    )
    monkeypatch.setattr(data_module, "_fetch_json", fake_fetch_json)

    overview = data_module.fetch_overview(date(2026, 1, 13))
    assert overview["health_score"] <= 100

    advanced = data_module.fetch_advanced_data(date(2026, 1, 13), date(2026, 1, 13))
    assert advanced["data_source"] == "api"
    assert advanced["anomalies_table"][0]["Method"] == "ewma"
