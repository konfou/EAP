import runpy

from apps.scheduler import app as scheduler_app


class DummyScheduler:
    def __init__(self, *args, **kwargs):
        self.jobs = []

    def add_job(self, func, *_args, **_kwargs):
        self.jobs.append(func)

    def start(self):
        return None


def test_run_all(monkeypatch):
    calls = []

    monkeypatch.setattr(scheduler_app, "run_dq", lambda: calls.append("dq"))
    monkeypatch.setattr(scheduler_app, "run_metrics", lambda: calls.append("metrics"))
    monkeypatch.setattr(scheduler_app, "run_anomaly", lambda: calls.append("anomaly"))
    monkeypatch.setattr(
        scheduler_app, "run_notifications", lambda: calls.append("notify")
    )

    scheduler_app.run_all()
    assert calls == ["dq", "metrics", "anomaly", "notify"]


def test_scheduler_main(monkeypatch):
    monkeypatch.setattr(scheduler_app, "run_all", lambda: None)
    monkeypatch.setattr(scheduler_app, "BlockingScheduler", DummyScheduler)
    scheduler_app.main()


def test_scheduler___main__(monkeypatch):
    monkeypatch.setattr(scheduler_app, "main", lambda: None)
    runpy.run_module("apps.scheduler.__main__", run_name="__main__")
