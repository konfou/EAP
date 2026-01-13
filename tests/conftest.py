import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/risk"
)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)

from apps.api.app import app  # noqa
from apps.api.db import get_db  # noqa

engine = create_engine(TEST_DB_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def prepare_db():
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS api_metrics (
                  id INT PRIMARY KEY DEFAULT 1,
                  total_requests BIGINT NOT NULL DEFAULT 0,
                  total_errors BIGINT NOT NULL DEFAULT 0,
                  total_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS anomaly_rules (
                  rule_name TEXT PRIMARY KEY,
                  rule_version TEXT NOT NULL,
                  config JSONB NOT NULL DEFAULT '{}'::jsonb,
                  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        config = {
            "ewma_lambda": 0.3,
            "ewma_limit": 3,
            "change_point_window": 7,
            "change_point_z": 3,
            "seasonal_min_points": 3,
            "seasonal_z": 3,
            "regime_recent_days": 7,
            "regime_baseline_days": 14,
            "regime_z": 3,
            "regime_var_ratio": 2,
        }
        conn.execute(
            text(
                """
                INSERT INTO anomaly_rules(rule_name, rule_version, config)
                VALUES (:rule_name, :rule_version, CAST(:config AS jsonb))
                ON CONFLICT (rule_name) DO NOTHING
                """
            ),
            {
                "rule_name": "anomaly_rules",
                "rule_version": "v1",
                "config": json.dumps(config),
            },
        )
        for table in [
            "events_raw",
            "events_quarantine",
            "metrics_daily",
            "dq_reports",
            "alerts",
            "api_metrics",
        ]:
            conn.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as conn:
        for table in [
            "events_raw",
            "events_quarantine",
            "metrics_daily",
            "dq_reports",
            "alerts",
            "api_metrics",
        ]:
            conn.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
