from apps.dashboard import components


def test_gauge_component():
    graph = components.gauge("Risk", 42, "#000")
    assert graph is not None


def test_badges():
    assert components.readiness_badge(True).children is not None
    assert components.source_badge("sql").children is not None
