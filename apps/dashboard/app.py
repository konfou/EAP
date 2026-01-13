"""Dash application wiring and callbacks."""

from datetime import date, datetime, timezone
from typing import Any

import dash
from dash import Input, Output, html

from .components import readiness_badge, source_badge
from .data import fetch_advanced_data
from .layout import build_layout


app = dash.Dash(__name__)
app.layout = build_layout
server = app.server


@app.callback(
    Output("dq-summary-text", "children"),
    Output("metrics-table", "data"),
    Output("alerts-table", "data"),
    Output("telemetry-table", "data"),
    Output("top-anomalies-table", "data"),
    Output("last-updated", "children"),
    Output("readiness-badge", "children"),
    Output("data-source-badge", "children"),
    Input("dashboard-refresh", "n_intervals"),
    Input("advanced-date-range", "start_date"),
    Input("advanced-date-range", "end_date"),
)
def update_advanced_panel(
    n_intervals: int, start_date: str, end_date: str
) -> tuple[
    list[html.Div],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    html.Div,
    html.Div,
]:
    start = date.fromisoformat(start_date) if start_date else date.today()
    end = date.fromisoformat(end_date) if end_date else date.today()
    advanced = fetch_advanced_data(start, end)
    telemetry_data = advanced["telemetry_table"]
    readiness = readiness_badge(advanced["readiness_ok"])
    source_indicator = source_badge(advanced["data_source"])
    dq_summary = advanced["dq_summary_text"]
    dq_cards = []
    if dq_summary and "|" in dq_summary:
        for chunk in dq_summary.split("|"):
            dq_cards.append(chunk.strip())
    else:
        dq_cards.append(dq_summary or "No DQ reports yet.")
    dq_summary_nodes = [
        html.Div(
            text,
            style={
                "background": "#f8fafc",
                "border": "1px solid #e2e8f0",
                "padding": "10px 12px",
                "borderRadius": "10px",
                "color": "#475569",
                "fontSize": "12px",
            },
        )
        for text in dq_cards
    ]
    return (
        dq_summary_nodes,
        advanced["metrics_table"] or [{"Metric": "No data", "Value": 0}],
        advanced["alerts_table"]
        or [
            {
                "Alert": "No recent alerts",
                "Severity": "INFO",
                "Risk": 0.0,
                "Status": "OPEN",
                "Timestamp": "",
            }
        ],
        telemetry_data,
        advanced["anomalies_table"],
        f"Last updated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        readiness,
        source_indicator,
    )
