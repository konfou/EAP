"""Reusable dashboard UI components."""

import plotly.graph_objects as go
from dash import dcc, html


def gauge(title: str, value: float, color: str) -> dcc.Graph:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "bgcolor": "white",
            },
        )
    )
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10))
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


def readiness_badge(is_ready: bool) -> html.Div:
    label = "Ready" if is_ready else "Not Ready"
    color = "#16a34a" if is_ready else "#dc2626"
    return html.Div(
        label,
        style={
            "padding": "6px 12px",
            "borderRadius": "999px",
            "backgroundColor": color,
            "color": "white",
            "fontSize": "12px",
            "fontWeight": "bold",
        },
    )


def source_badge(source: str) -> html.Div:
    label = f"Data source: {source.upper()}"
    color = "#2563eb" if source.lower() == "api" else "#0f766e"
    return html.Div(
        label,
        style={
            "padding": "6px 12px",
            "borderRadius": "999px",
            "backgroundColor": color,
            "color": "white",
            "fontSize": "12px",
            "fontWeight": "bold",
        },
    )
