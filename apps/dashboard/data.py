"""Dashboard data access and aggregation helpers."""

from datetime import date, timedelta
from typing import Any

import json
import os
import urllib.request

from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/risk")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
USE_API = os.getenv("DASHBOARD_DATA_SOURCE", "sql").lower() == "api"
engine = create_engine(DB_URL, pool_pre_ping=True)


def fetch_overview(target_date: date) -> dict[str, Any]:
    metrics = ["tx_fail_rate", "latency_p95_ms", "tx_completed_value", "dau"]

    if USE_API:
        return _fetch_overview_api(target_date, metrics)
    return _fetch_overview_sql(target_date, metrics)


def _fetch_overview_api(target_date: date, metrics: list[str]) -> dict[str, Any]:
    dq_data = _fetch_json(f"{API_BASE_URL}/dq/latest") or {}
    dq_summary = dq_data.get("summary", {})
    dq_confidence = float(dq_summary.get("confidence", 0.0)) * 100
    dq_pass = bool(dq_data.get("pass", False))

    alerts_data = _fetch_json(f"{API_BASE_URL}/alerts/recent") or []
    notifications_data = _fetch_json(f"{API_BASE_URL}/alerts/notifications") or []
    top_risks = [
        {
            "metric_name": row.get("metric_name"),
            "severity": row.get("severity"),
            "risk_score": row.get("risk_score"),
            "message": row.get("message"),
            "context": row.get("context"),
        }
        for row in alerts_data[:5]
    ]
    open_alerts = len([row for row in alerts_data if row.get("status") == "OPEN"])

    metric_groups: dict[str, list[float]] = {}
    start_date = target_date - timedelta(days=6)
    for metric_name in metrics:
        metrics_data = _fetch_json(
            f"{API_BASE_URL}/metrics/daily?metric={metric_name}&date_from={start_date}&date_to={target_date}"
        )
        if metrics_data:
            metric_groups[metric_name] = [
                float(row.get("value", 0)) for row in metrics_data
            ]

    stability_scores = []
    for values in metric_groups.values():
        if len(values) < 2:
            continue
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            continue
        variance = sum((val - mean_val) ** 2 for val in values) / (len(values) - 1)
        stdev = variance**0.5
        stability_scores.append(stdev / abs(mean_val))
    stability_index = 100.0
    if stability_scores:
        stability_index = max(0.0, 100.0 - min(100.0, sum(stability_scores) * 100))

    financial_exposure = sum(
        float(row.get("context", {}).get("impact", 0)) for row in alerts_data
    )

    health_penalty = min(60, open_alerts * 8)
    if not dq_pass:
        health_penalty += 15
    health_score = max(0, min(100, 100 - health_penalty))

    return {
        "health_score": health_score,
        "top_risks": top_risks,
        "stability_index": stability_index,
        "dq_confidence": dq_confidence,
        "financial_exposure": float(financial_exposure),
    }


def _fetch_overview_sql(target_date: date, metrics: list[str]) -> dict[str, Any]:
    with engine.begin() as conn:
        dq_row = (
            conn.execute(
                text(
                    """
                SELECT report_date, pass, summary
                FROM dq_reports
                WHERE report_date <= CAST(:d AS date)
                ORDER BY report_date DESC
                LIMIT 1
                """
                ),
                {"d": target_date},
            )
            .mappings()
            .first()
        )
        dq_confidence = 0.0
        dq_pass = False
        if dq_row:
            dq_pass = bool(dq_row["pass"])
            dq_confidence = float(dq_row["summary"].get("confidence", 0.0))

        alert_counts = (
            conn.execute(
                text(
                    """
                SELECT status, COUNT(*) AS n
                FROM alerts
                WHERE (metric_date = :d OR (metric_date IS NULL AND ts::date = :d))
                GROUP BY status
                """
                ),
                {"d": target_date},
            )
            .mappings()
            .all()
        )
        alert_count_map = {row["status"]: int(row["n"]) for row in alert_counts}
        open_alerts = alert_count_map.get("OPEN", 0)

        top_risks = (
            conn.execute(
                text(
                    """
                SELECT metric_name, severity, risk_score, message
                FROM alerts
                WHERE (metric_date = :d OR (metric_date IS NULL AND ts::date = :d))
                ORDER BY risk_score DESC
                LIMIT 5
                """
                ),
                {"d": target_date},
            )
            .mappings()
            .all()
        )

        metric_rows = (
            conn.execute(
                text(
                    """
                SELECT metric_name, value
                FROM metrics_daily
                WHERE metric_name = ANY(:metrics)
                  AND metric_date >= CAST(:d0 AS date)
                  AND metric_date <= CAST(:d1 AS date)
                """
                ),
                {
                    "metrics": metrics,
                    "d0": target_date - timedelta(days=6),
                    "d1": target_date,
                },
            )
            .mappings()
            .all()
        )

        metric_groups: dict[str, list[float]] = {}
        for row in metric_rows:
            metric_groups.setdefault(row["metric_name"], []).append(float(row["value"]))

        stability_scores = []
        for values in metric_groups.values():
            if len(values) < 2:
                continue
            mean_val = sum(values) / len(values)
            if mean_val == 0:
                continue
            variance = sum((val - mean_val) ** 2 for val in values) / (len(values) - 1)
            stdev = variance**0.5
            stability_scores.append(stdev / abs(mean_val))
        stability_index = 100.0
        if stability_scores:
            stability_index = max(0.0, 100.0 - min(100.0, sum(stability_scores) * 100))

        financial_exposure = conn.execute(
            text(
                """
                SELECT COALESCE(SUM((context->>'impact')::double precision), 0) AS total
                FROM alerts
                WHERE (metric_date = :d OR (metric_date IS NULL AND ts::date = :d))
                """
            ),
            {"d": target_date},
        ).scalar()

    health_penalty = min(60, open_alerts * 8)
    if not dq_pass:
        health_penalty += 15
    health_score = max(0, min(100, 100 - health_penalty))

    return {
        "health_score": health_score,
        "top_risks": top_risks,
        "stability_index": stability_index,
        "dq_confidence": dq_confidence * 100,
        "financial_exposure": float(financial_exposure),
    }


def _fetch_json(url: str) -> Any | None:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def fetch_advanced_data(start_date: date, end_date: date) -> dict[str, Any]:
    if USE_API:
        return _fetch_advanced_data_api(start_date, end_date)
    return _fetch_advanced_data_sql(start_date, end_date)


def _fetch_advanced_data_api(start_date: date, end_date: date) -> dict[str, Any]:
    readiness_ok = False
    readiness_response = _fetch_json(f"{API_BASE_URL}/ready")
    if readiness_response and readiness_response.get("ok"):
        readiness_ok = True

    health_ok = False
    health_response = _fetch_json(f"{API_BASE_URL}/health")
    if health_response and health_response.get("ok"):
        health_ok = True

    metrics_response = _fetch_json(f"{API_BASE_URL}/metrics") or {}
    prometheus_sample = None
    try:
        with urllib.request.urlopen(
            f"{API_BASE_URL}/metrics/prometheus", timeout=2
        ) as response:
            lines = response.read().decode("utf-8").splitlines()
            prometheus_sample = next(
                (line for line in lines if line and not line.startswith("#")),
                None,
            )
    except Exception:
        prometheus_sample = None

    dq_data = _fetch_json(f"{API_BASE_URL}/dq/latest") or {}
    dq_summary = dq_data.get("summary", {})
    dq_summary_text = (
        f"{dq_data.get('report_date')} | pass={dq_data.get('pass')} | "
        f"confidence={dq_summary.get('confidence', 0):.2f}"
        if dq_data
        else "No DQ reports yet."
    )

    alerts_data = _fetch_json(f"{API_BASE_URL}/alerts/recent") or []

    metrics_table = []
    for metric_name in ["tx_fail_rate", "latency_p95_ms", "tx_completed_value", "dau"]:
        metric_rows = _fetch_json(
            f"{API_BASE_URL}/metrics/daily?metric={metric_name}&date_from={end_date}&date_to={end_date}"
        )
        if metric_rows:
            metrics_table.append(
                {
                    "Metric": metric_name,
                    "Value": round(float(metric_rows[-1].get("value", 0)), 4),
                }
            )
    alerts_table = [
        {
            "Alert": row.get("metric_name", ""),
            "Severity": row.get("severity", ""),
            "Risk": round(float(row.get("risk_score", 0)), 2),
            "Status": row.get("status", ""),
            "Timestamp": row.get("ts", ""),
        }
        for row in alerts_data
    ]
    notifications_table = [
        {
            "Channel": row.get("channel", ""),
            "Target": row.get("target", ""),
            "Status": row.get("status", ""),
            "Alert": row.get("metric_name", ""),
            "Severity": row.get("severity", ""),
            "Sent At": row.get("sent_at") or row.get("created_at", ""),
        }
        for row in notifications_data
    ]
    if not notifications_table:
        notifications_table = [
            {
                "Channel": "-",
                "Target": "-",
                "Status": "n/a",
                "Alert": "No notifications",
                "Severity": "",
                "Sent At": "",
            }
        ]

    telemetry_table = [
        {
            "Metric": "total_requests",
            "Value": metrics_response.get("total_requests", 0),
        },
        {
            "Metric": "total_errors",
            "Value": metrics_response.get("total_errors", 0),
        },
        {
            "Metric": "avg_latency_ms",
            "Value": metrics_response.get("avg_latency_ms", 0.0),
        },
        {
            "Metric": "readiness",
            "Value": "ready" if readiness_ok else "not ready",
        },
        {
            "Metric": "health",
            "Value": "ok" if health_ok else "unavailable",
        },
        {
            "Metric": "prometheus_sample",
            "Value": prometheus_sample or "unavailable",
        },
    ]

    anomalies_table = [
        {
            "Metric": row.get("metric_name", ""),
            "Impact": round(float(row.get("context", {}).get("impact", 0)), 2),
            "Method": row.get("context", {}).get("method", "n/a"),
            "Timestamp": row.get("ts", ""),
        }
        for row in alerts_data[:5]
    ]
    if not anomalies_table:
        anomalies_table = [
            {
                "Metric": "No anomalies",
                "Impact": 0.0,
                "Method": "n/a",
                "Timestamp": "",
            }
        ]

    return {
        "dq_summary_text": dq_summary_text,
        "metrics_table": metrics_table,
        "alerts_table": alerts_table,
        "notifications_table": notifications_table,
        "anomalies_table": anomalies_table,
        "telemetry_table": telemetry_table,
        "readiness_ok": readiness_ok,
        "data_source": "api",
    }


def _fetch_advanced_data_sql(start_date: date, end_date: date) -> dict[str, Any]:
    readiness_ok = False
    readiness_response = _fetch_json(f"{API_BASE_URL}/ready")
    if readiness_response and readiness_response.get("ok"):
        readiness_ok = True

    health_ok = False
    health_response = _fetch_json(f"{API_BASE_URL}/health")
    if health_response and health_response.get("ok"):
        health_ok = True

    metrics_response = _fetch_json(f"{API_BASE_URL}/metrics") or {}
    prometheus_sample = None
    try:
        with urllib.request.urlopen(
            f"{API_BASE_URL}/metrics/prometheus", timeout=2
        ) as response:
            lines = response.read().decode("utf-8").splitlines()
            prometheus_sample = next(
                (line for line in lines if line and not line.startswith("#")),
                None,
            )
    except Exception:
        prometheus_sample = None
    with engine.begin() as conn:
        latest_dq = (
            conn.execute(
                text(
                    """
                SELECT report_date::text, pass, summary
                FROM dq_reports
                WHERE report_date <= CAST(:end_date AS date)
                ORDER BY report_date DESC
                LIMIT 1
                """
                ),
                {"end_date": end_date},
            )
            .mappings()
            .first()
        )
        metrics_snapshot = (
            conn.execute(
                text(
                    """
                SELECT metric_name, value
                FROM metrics_daily
                WHERE metric_date = (
                    SELECT MAX(metric_date)
                    FROM metrics_daily
                    WHERE metric_date >= CAST(:start_date AS date)
                      AND metric_date <= CAST(:end_date AS date)
                )
                ORDER BY metric_name
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )
            .mappings()
            .all()
        )
        alerts_window = (
            conn.execute(
                text(
                    """
                SELECT metric_name, severity, risk_score, status, ts::text
                FROM alerts
                WHERE COALESCE(metric_date, ts::date) >= CAST(:start_date AS date)
                  AND COALESCE(metric_date, ts::date) <= CAST(:end_date AS date)
                ORDER BY ts DESC
                LIMIT 10
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )
            .mappings()
            .all()
        )

        top_anomalies = (
            conn.execute(
                text(
                    """
                SELECT metric_name,
                       COALESCE((context->>'impact')::double precision, 0) AS impact,
                       context->>'method' AS method,
                       ts::text AS ts
                FROM alerts
                WHERE COALESCE(metric_date, ts::date) >= CAST(:start_date AS date)
                  AND COALESCE(metric_date, ts::date) <= CAST(:end_date AS date)
                ORDER BY impact DESC
                LIMIT 5
                """
                ),
                {"start_date": start_date, "end_date": end_date},
            )
            .mappings()
            .all()
        )

        notifications_window = (
            conn.execute(
                text(
                    """
                SELECT n.channel,
                       n.target,
                       n.status,
                       n.sent_at::text AS sent_at,
                       n.created_at::text AS created_at,
                       a.metric_name,
                       a.severity
                FROM alert_notifications n
                LEFT JOIN alerts a ON a.alert_id = n.alert_id
                ORDER BY n.created_at DESC
                LIMIT 10
                """
                )
            )
            .mappings()
            .all()
        )

    dq_summary = latest_dq["summary"] if latest_dq else {}
    dq_summary_text = (
        f"{latest_dq['report_date']} | pass={latest_dq['pass']} | "
        f"confidence={dq_summary.get('confidence', 0):.2f}"
        if latest_dq
        else "No DQ reports yet."
    )

    metrics_table = [
        {"Metric": row["metric_name"], "Value": round(float(row["value"]), 4)}
        for row in metrics_snapshot
    ]
    alerts_table = [
        {
            "Alert": row["metric_name"],
            "Severity": row["severity"],
            "Risk": round(float(row["risk_score"]), 2),
            "Status": row["status"],
            "Timestamp": row["ts"],
        }
        for row in alerts_window
    ]

    anomalies_table = [
        {
            "Metric": row["metric_name"],
            "Impact": round(float(row["impact"]), 2),
            "Method": row["method"] or "n/a",
            "Timestamp": row["ts"],
        }
        for row in top_anomalies
    ]
    if not anomalies_table:
        anomalies_table = [
            {
                "Metric": "No anomalies",
                "Impact": 0.0,
                "Method": "n/a",
                "Timestamp": "",
            }
        ]

    notifications_table = [
        {
            "Channel": row["channel"],
            "Target": row["target"],
            "Status": row["status"],
            "Alert": row.get("metric_name") or "",
            "Severity": row.get("severity") or "",
            "Sent At": row.get("sent_at") or row.get("created_at") or "",
        }
        for row in notifications_window
    ]
    if not notifications_table:
        notifications_table = [
            {
                "Channel": "-",
                "Target": "-",
                "Status": "n/a",
                "Alert": "No notifications",
                "Severity": "",
                "Sent At": "",
            }
        ]

    telemetry_table = [
        {
            "Metric": "total_requests",
            "Value": metrics_response.get("total_requests", 0),
        },
        {
            "Metric": "total_errors",
            "Value": metrics_response.get("total_errors", 0),
        },
        {
            "Metric": "avg_latency_ms",
            "Value": metrics_response.get("avg_latency_ms", 0.0),
        },
        {
            "Metric": "readiness",
            "Value": "ready" if readiness_ok else "not ready",
        },
        {
            "Metric": "health",
            "Value": "ok" if health_ok else "unavailable",
        },
        {
            "Metric": "prometheus_sample",
            "Value": prometheus_sample or "unavailable",
        },
    ]

    return {
        "dq_summary_text": dq_summary_text,
        "metrics_table": metrics_table,
        "alerts_table": alerts_table,
        "notifications_table": notifications_table,
        "anomalies_table": anomalies_table,
        "telemetry_table": telemetry_table,
        "readiness_ok": readiness_ok,
        "data_source": "sql",
    }
