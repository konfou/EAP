import runpy

from apps.dashboard import main as dashboard_main


def test_dashboard_main(monkeypatch):
    monkeypatch.setattr(dashboard_main.app, "run", lambda **kwargs: None)
    dashboard_main.main()


def test_dashboard___main__(monkeypatch):
    monkeypatch.setattr(dashboard_main, "main", lambda: None)
    runpy.run_module("apps.dashboard.__main__", run_name="__main__")
