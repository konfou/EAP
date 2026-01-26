from apps.dashboard import components


def test_gauge_component():
    graph = components.gauge("Risk", 42, "#000")
    assert graph.figure["data"][0]["value"] == 42


def test_badges():
    assert "Ready" in components.readiness_badge(True).children
    assert "SQL" in components.source_badge("sql").children
