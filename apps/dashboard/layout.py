"""Dashboard layout definition."""

from datetime import date, timedelta

from dash import dash_table, dcc, html

from .components import gauge, readiness_badge, source_badge
from .data import fetch_advanced_data, fetch_overview


def build_layout() -> html.Div:
    today = date.today()
    overview = fetch_overview(today)
    advanced_data = fetch_advanced_data(today - timedelta(days=7), today)

    top_risks = [
        {
            "Risk": row["metric_name"],
            "Severity": row["severity"],
            "Score": round(float(row["risk_score"]), 2),
            "Summary": row["message"],
        }
        for row in overview["top_risks"]
    ]
    if not top_risks:
        top_risks = [
            {
                "Risk": "No material risks",
                "Severity": "INFO",
                "Score": 0.0,
                "Summary": "Operating within expected thresholds.",
            }
        ]

    return html.Div(
        style={
            "fontFamily": "Arial, sans-serif",
            "backgroundColor": "#f5f7fb",
            "padding": "32px",
            "color": "#0f172a",
        },
        children=[
            dcc.Interval(id="dashboard-refresh", interval=60_000, n_intervals=0),
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                },
                children=[
                    html.Div(
                        children=[
                            html.H1(
                                "Executive Risk Dashboard",
                                style={"marginBottom": "8px"},
                            ),
                            html.P(
                                "Daily operational posture with clear, decision-ready signals.",
                                style={"marginTop": 0, "color": "#475569"},
                            ),
                        ]
                    ),
                    html.Div(
                        id="readiness-badge",
                        children=readiness_badge(advanced_data["readiness_ok"]),
                    ),
                ],
            ),
            html.Div(
                id="last-updated",
                style={"color": "#64748b", "marginTop": "4px"},
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
                    "gap": "16px",
                    "marginTop": "24px",
                },
                children=[
                    gauge(
                        "Operational Health Score",
                        overview["health_score"],
                        "#0f766e",
                    ),
                    gauge(
                        "Trend Stability Index",
                        overview["stability_index"],
                        "#1d4ed8",
                    ),
                    gauge(
                        "Data Quality Confidence",
                        overview["dq_confidence"],
                        "#7c3aed",
                    ),
                    html.Div(
                        style={
                            "background": "white",
                            "padding": "20px",
                            "borderRadius": "12px",
                            "boxShadow": "0 2px 8px rgba(15, 23, 42, 0.08)",
                            "display": "flex",
                            "flexDirection": "column",
                            "justifyContent": "center",
                        },
                        children=[
                            html.Div(
                                "Financial Exposure Estimate",
                                style={"fontSize": "14px", "color": "#64748b"},
                            ),
                            html.Div(
                                f"${overview['financial_exposure']:,.0f}",
                                style={
                                    "fontSize": "32px",
                                    "fontWeight": "bold",
                                    "marginTop": "6px",
                                },
                            ),
                            html.Div(
                                "Based on today’s highest-impact signals.",
                                style={"fontSize": "12px", "color": "#94a3b8"},
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                style={
                    "marginTop": "32px",
                    "background": "white",
                    "padding": "20px",
                    "borderRadius": "12px",
                    "boxShadow": "0 2px 8px rgba(15, 23, 42, 0.08)",
                },
                children=[
                    html.H2("Top Risks Today", style={"marginTop": 0}),
                    dash_table.DataTable(
                        data=top_risks,
                        columns=[
                            {"name": "Risk", "id": "Risk"},
                            {"name": "Severity", "id": "Severity"},
                            {"name": "Score", "id": "Score"},
                            {"name": "Summary", "id": "Summary"},
                        ],
                        style_header={
                            "backgroundColor": "#f8fafc",
                            "fontWeight": "bold",
                            "color": "#0f172a",
                        },
                        style_cell={
                            "padding": "8px",
                            "fontFamily": "Arial",
                            "whiteSpace": "normal",
                            "height": "auto",
                        },
                        style_table={"overflowX": "auto"},
                    ),
                ],
            ),
            html.Div(
                style={
                    "marginTop": "24px",
                    "background": "white",
                    "padding": "20px",
                    "borderRadius": "12px",
                    "boxShadow": "0 2px 8px rgba(15, 23, 42, 0.08)",
                },
                children=[
                    html.H2("Top Anomalies by Impact", style={"marginTop": 0}),
                    dash_table.DataTable(
                        id="top-anomalies-table",
                        data=advanced_data["anomalies_table"],
                        columns=[
                            {"name": "Metric", "id": "Metric"},
                            {"name": "Impact", "id": "Impact"},
                            {"name": "Method", "id": "Method"},
                            {"name": "Timestamp", "id": "Timestamp"},
                        ],
                        style_header={
                            "backgroundColor": "#f8fafc",
                            "fontWeight": "bold",
                            "color": "#0f172a",
                        },
                        style_cell={
                            "padding": "8px",
                            "fontFamily": "Arial",
                            "whiteSpace": "normal",
                            "height": "auto",
                        },
                        style_table={"overflowX": "auto"},
                    ),
                ],
            ),
            html.Details(
                style={"marginTop": "24px"},
                children=[
                    html.Summary(
                        "Advanced Panel: Full API Coverage",
                        style={
                            "fontWeight": "bold",
                            "cursor": "pointer",
                            "color": "#1f2937",
                        },
                    ),
                    html.Div(
                        style={
                            "marginTop": "12px",
                            "background": "white",
                            "padding": "20px",
                            "borderRadius": "12px",
                            "boxShadow": "0 2px 8px rgba(15, 23, 42, 0.08)",
                        },
                        children=[
                            html.Div(
                                style={
                                    "display": "flex",
                                    "gap": "16px",
                                    "alignItems": "center",
                                    "flexWrap": "wrap",
                                },
                                children=[
                                    html.Div(
                                        style={
                                            "background": "#f8fafc",
                                            "padding": "12px 16px",
                                            "borderRadius": "10px",
                                            "border": "1px solid #e2e8f0",
                                        },
                                        children=[
                                            html.Label(
                                                "Date Range",
                                                style={
                                                    "display": "block",
                                                    "fontSize": "12px",
                                                    "color": "#64748b",
                                                    "marginBottom": "6px",
                                                },
                                            ),
                                            dcc.DatePickerRange(
                                                id="advanced-date-range",
                                                start_date=(
                                                    today - timedelta(days=7)
                                                ).isoformat(),
                                                end_date=today.isoformat(),
                                                display_format="YYYY-MM-DD",
                                                style={"fontSize": "12px"},
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        style={
                                            "background": "#f8fafc",
                                            "padding": "12px 16px",
                                            "borderRadius": "10px",
                                            "border": "1px solid #e2e8f0",
                                        },
                                        children=[
                                            html.Label(
                                                "Mode",
                                                style={
                                                    "display": "block",
                                                    "fontSize": "12px",
                                                    "color": "#64748b",
                                                    "marginBottom": "6px",
                                                },
                                            ),
                                            html.Div(
                                                id="data-source-badge",
                                                children=source_badge(
                                                    advanced_data["data_source"]
                                                ),
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.H3(
                                "Data Quality Snapshot", style={"marginTop": "16px"}
                            ),
                            html.Div(
                                id="dq-summary-text",
                                style={
                                    "display": "grid",
                                    "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
                                    "gap": "12px",
                                },
                            ),
                            html.H3("Latest Metrics"),
                            dash_table.DataTable(
                                id="metrics-table",
                                data=advanced_data["metrics_table"]
                                or [{"Metric": "No data", "Value": 0}],
                                columns=[
                                    {"name": "Metric", "id": "Metric"},
                                    {"name": "Value", "id": "Value"},
                                ],
                                style_header={
                                    "backgroundColor": "#f8fafc",
                                    "fontWeight": "bold",
                                    "color": "#0f172a",
                                },
                                style_cell={
                                    "padding": "8px",
                                    "fontFamily": "Arial",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                },
                                style_table={"overflowX": "auto"},
                            ),
                            html.H3("Recent Alerts"),
                            dash_table.DataTable(
                                id="alerts-table",
                                data=advanced_data["alerts_table"]
                                or [
                                    {
                                        "Alert": "No recent alerts",
                                        "Severity": "INFO",
                                        "Risk": 0.0,
                                        "Status": "OPEN",
                                        "Timestamp": "",
                                    }
                                ],
                                columns=[
                                    {"name": "Alert", "id": "Alert"},
                                    {"name": "Severity", "id": "Severity"},
                                    {"name": "Risk", "id": "Risk"},
                                    {"name": "Status", "id": "Status"},
                                    {"name": "Timestamp", "id": "Timestamp"},
                                ],
                                style_header={
                                    "backgroundColor": "#f8fafc",
                                    "fontWeight": "bold",
                                    "color": "#0f172a",
                                },
                                style_cell={
                                    "padding": "8px",
                                    "fontFamily": "Arial",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                },
                                style_table={"overflowX": "auto"},
                            ),
                            html.H3("Notification Routing"),
                            dash_table.DataTable(
                                id="notifications-table",
                                data=advanced_data["notifications_table"],
                                columns=[
                                    {"name": "Channel", "id": "Channel"},
                                    {"name": "Target", "id": "Target"},
                                    {"name": "Status", "id": "Status"},
                                    {"name": "Alert", "id": "Alert"},
                                    {"name": "Severity", "id": "Severity"},
                                    {"name": "Sent At", "id": "Sent At"},
                                ],
                                style_header={
                                    "backgroundColor": "#f8fafc",
                                    "fontWeight": "bold",
                                    "color": "#0f172a",
                                },
                                style_cell={
                                    "padding": "8px",
                                    "fontFamily": "Arial",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                },
                                style_table={"overflowX": "auto"},
                            ),
                            html.H3("Service Telemetry"),
                            dash_table.DataTable(
                                id="telemetry-table",
                                data=advanced_data["telemetry_table"],
                                columns=[
                                    {"name": "Metric", "id": "Metric"},
                                    {"name": "Value", "id": "Value"},
                                ],
                                style_header={
                                    "backgroundColor": "#f8fafc",
                                    "fontWeight": "bold",
                                    "color": "#0f172a",
                                },
                                style_cell={
                                    "padding": "8px",
                                    "fontFamily": "Arial",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                },
                                style_table={"overflowX": "auto"},
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
