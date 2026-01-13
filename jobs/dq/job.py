"""Data quality controls mapped to physics-style measurement validation."""

import json
import math
import os
from datetime import date, timedelta

import numpy as np
from sqlalchemy import create_engine, text

from eap.logging import configure_logging

DB = os.environ["DATABASE_URL"]
engine = create_engine(DB, pool_pre_ping=True)
logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))

REQUIRED_FIELDS = ["event_id", "ts_event", "event_type", "source_system"]
KS_MIN_SAMPLES = 20
KS_P_THRESHOLD = 0.05
SOURCE_BIAS_Z_THRESHOLD = 2.5
COMPLETENESS_THRESHOLD = 0.99
QUARANTINE_RATE_THRESHOLD = 0.01


def ks_test(sample_x: list[float], sample_y: list[float]) -> tuple[float, float]:
    """Return Kolmogorov-Smirnov statistic and approximate p-value."""
    xs = np.sort(np.asarray(sample_x))
    ys = np.sort(np.asarray(sample_y))
    count_x = len(xs)
    count_y = len(ys)
    data = np.sort(np.concatenate([xs, ys]))
    cdf_x = np.searchsorted(xs, data, side="right") / count_x
    cdf_y = np.searchsorted(ys, data, side="right") / count_y
    statistic = float(np.max(np.abs(cdf_x - cdf_y)))
    en = math.sqrt(count_x * count_y / (count_x + count_y))
    lam = (en + 0.12 + 0.11 / en) * statistic
    p_value = 0.0
    for term_index in range(1, 100):
        term = 2 * (-1) ** (term_index - 1) * math.exp(-2 * (lam**2) * (term_index**2))
        p_value += term
        if abs(term) < 1e-6:
            break
    p_value = max(0.0, min(1.0, p_value))
    return statistic, p_value


def dq_confidence(
    n_events: int, completeness_rate: float, quarantine_rate: float
) -> float:
    """Blend volume and cleanliness into a [0,1] confidence score."""
    if n_events <= 0:
        return 0.0
    volume_score = min(1.0, math.log10(n_events + 1) / 4)
    cleanliness_score = max(0.0, 1.0 - quarantine_rate)
    return max(
        0.0,
        min(
            1.0,
            (0.6 * volume_score + 0.4 * completeness_rate) * cleanliness_score,
        ),
    )


def fetch_totals(conn, report_date: date) -> dict:
    """Count events and duplicates for the report date."""
    row = (
        conn.execute(
            text("""
        SELECT
          COUNT(*) AS n,
          COUNT(DISTINCT event_id) AS n_distinct
        FROM events_raw
        WHERE ts_event >= CAST(:d AS date)
          AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """),
            {"d": report_date},
        )
        .mappings()
        .first()
    )
    event_count = int(row["n"])
    duplicates = max(0, event_count - int(row["n_distinct"]))
    return {"n_events": event_count, "duplicate_events": duplicates}


def fetch_missing_required(conn, report_date: date) -> dict:
    """Count missing required measurements per field."""
    row = (
        conn.execute(
            text("""
        SELECT
          SUM(CASE WHEN event_id IS NULL THEN 1 ELSE 0 END) AS event_id_missing,
          SUM(CASE WHEN ts_event IS NULL THEN 1 ELSE 0 END) AS ts_event_missing,
          SUM(CASE WHEN event_type IS NULL THEN 1 ELSE 0 END) AS event_type_missing,
          SUM(CASE WHEN source_system IS NULL THEN 1 ELSE 0 END) AS source_system_missing
        FROM events_raw
        WHERE ts_event >= CAST(:d AS date)
          AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """),
            {"d": report_date},
        )
        .mappings()
        .first()
    )
    total = int(
        (row["event_id_missing"] or 0)
        + (row["ts_event_missing"] or 0)
        + (row["event_type_missing"] or 0)
        + (row["source_system_missing"] or 0)
    )
    return {
        "event_id": int(row["event_id_missing"] or 0),
        "ts_event": int(row["ts_event_missing"] or 0),
        "event_type": int(row["event_type_missing"] or 0),
        "source_system": int(row["source_system_missing"] or 0),
        "total": total,
    }


def compute_completeness_rate(n_events: int, missing_required_total: int) -> float:
    """Compute completeness rate from missing required fields."""
    if n_events <= 0:
        return 0.0
    return 1.0 - (missing_required_total / (n_events * len(REQUIRED_FIELDS)))


def fetch_freshness(conn, report_date: date) -> dict:
    """Compute ingestion lag percentiles for the report date."""
    row = (
        conn.execute(
            text("""
        SELECT
          PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (ts_ingested - ts_event))) AS p50_sec,
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (ts_ingested - ts_event))) AS p95_sec
        FROM events_raw
        WHERE ts_event >= CAST(:d AS date)
          AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
    """),
            {"d": report_date},
        )
        .mappings()
        .first()
    )
    return {
        "freshness_p50_sec": float(row["p50_sec"])
        if row["p50_sec"] is not None
        else None,
        "freshness_p95_sec": float(row["p95_sec"])
        if row["p95_sec"] is not None
        else None,
    }


def fetch_future_events(conn) -> int:
    """Count events timestamped unreasonably far in the future."""
    row = (
        conn.execute(
            text("""
        SELECT COUNT(*) AS n_future
        FROM events_raw
        WHERE ts_event > NOW() + INTERVAL '5 minutes'
    """)
        )
        .mappings()
        .first()
    )
    return int(row["n_future"])


def fetch_quarantine_stats(conn, report_date: date) -> dict:
    """Summarize quarantined payloads, separating malformed from duplicates."""
    rows = (
        conn.execute(
            text("""
        SELECT reason, COUNT(*) AS n
        FROM events_quarantine
        WHERE ts_ingested >= CAST(:d AS date)
          AND ts_ingested < (CAST(:d AS date) + INTERVAL '1 day')
        GROUP BY reason
    """),
            {"d": report_date},
        )
        .mappings()
        .all()
    )
    by_reason = {row["reason"]: int(row["n"]) for row in rows}
    total = int(sum(by_reason.values()))
    malformed_total = total - int(by_reason.get("duplicate_event_id", 0))
    return {
        "quarantine_total": total,
        "quarantine_by_reason": by_reason,
        "malformed_events": max(0, malformed_total),
    }


def fetch_schema_keys(conn, report_date: date) -> list[dict]:
    """Return most common property keys as a schema-drift proxy."""
    rows = (
        conn.execute(
            text("""
        SELECT key, COUNT(*) AS c
        FROM (
          SELECT jsonb_object_keys(properties) AS key
          FROM events_raw
          WHERE ts_event >= CAST(:d AS date)
            AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
        ) t
        GROUP BY key
        ORDER BY c DESC
        LIMIT 20
    """),
            {"d": report_date},
        )
        .mappings()
        .all()
    )
    return [{"key": row["key"], "count": int(row["c"])} for row in rows]


def fetch_distribution_drift(conn, report_date: date) -> list[dict]:
    """Detect distribution drift with a KS test versus prior week."""
    drift_checks = []
    drift_targets = {
        "transaction_value": "transaction_completed",
        "latency_value": "system_latency",
    }
    for name, event_type in drift_targets.items():
        current_vals = (
            conn.execute(
                text("""
            SELECT value
            FROM events_raw
            WHERE event_type = :event_type
              AND value IS NOT NULL
              AND ts_event >= CAST(:d AS date)
              AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
        """),
                {"event_type": event_type, "d": report_date},
            )
            .scalars()
            .all()
        )
        baseline_vals = (
            conn.execute(
                text("""
            SELECT value
            FROM events_raw
            WHERE event_type = :event_type
              AND value IS NOT NULL
              AND ts_event >= CAST(:d0 AS date)
              AND ts_event < CAST(:d1 AS date)
        """),
                {
                    "event_type": event_type,
                    "d0": report_date - timedelta(days=7),
                    "d1": report_date,
                },
            )
            .scalars()
            .all()
        )
        if len(current_vals) >= KS_MIN_SAMPLES and len(baseline_vals) >= KS_MIN_SAMPLES:
            d_stat, p_val = ks_test(current_vals, baseline_vals)
            drift_checks.append(
                {
                    "name": name,
                    "event_type": event_type,
                    "n_current": len(current_vals),
                    "n_baseline": len(baseline_vals),
                    "ks_stat": d_stat,
                    "p_value": p_val,
                    "drifted": p_val < KS_P_THRESHOLD,
                }
            )
    return drift_checks


def fetch_source_bias(conn, report_date: date) -> list[dict]:
    """Detect shifts in source_system contribution shares."""
    baseline_totals = (
        conn.execute(
            text("""
        SELECT CAST(ts_event AS date) AS d, COUNT(*) AS n
        FROM events_raw
        WHERE ts_event >= CAST(:d0 AS date)
          AND ts_event < CAST(:d1 AS date)
        GROUP BY CAST(ts_event AS date)
    """),
            {"d0": report_date - timedelta(days=7), "d1": report_date},
        )
        .mappings()
        .all()
    )
    baseline_total_by_day = {
        row["d"]: int(row["n"]) for row in baseline_totals if row["n"]
    }
    baseline_source_counts = (
        conn.execute(
            text("""
        SELECT source_system, CAST(ts_event AS date) AS d, COUNT(*) AS n
        FROM events_raw
        WHERE ts_event >= CAST(:d0 AS date)
          AND ts_event < CAST(:d1 AS date)
        GROUP BY source_system, CAST(ts_event AS date)
    """),
            {"d0": report_date - timedelta(days=7), "d1": report_date},
        )
        .mappings()
        .all()
    )
    baseline_source_shares: dict[str, list[float]] = {}
    for row in baseline_source_counts:
        day_total = baseline_total_by_day.get(row["d"])
        if not day_total:
            continue
        share = row["n"] / day_total
        baseline_source_shares.setdefault(row["source_system"], []).append(share)

    current_source_counts = (
        conn.execute(
            text("""
        SELECT source_system, COUNT(*) AS n
        FROM events_raw
        WHERE ts_event >= CAST(:d AS date)
          AND ts_event < (CAST(:d AS date) + INTERVAL '1 day')
        GROUP BY source_system
    """),
            {"d": report_date},
        )
        .mappings()
        .all()
    )
    current_total = int(sum(row["n"] for row in current_source_counts))
    source_bias = []
    if current_total:
        for row in current_source_counts:
            shares = baseline_source_shares.get(row["source_system"], [])
            if len(shares) < 3:
                continue
            mean_share = float(np.mean(shares))
            std_share = float(np.std(shares, ddof=1)) if len(shares) > 1 else 0.0
            if std_share <= 0:
                continue
            current_share = float(row["n"]) / current_total
            z_score = (current_share - mean_share) / std_share
            if abs(z_score) >= SOURCE_BIAS_Z_THRESHOLD:
                source_bias.append(
                    {
                        "source_system": row["source_system"],
                        "current_share": current_share,
                        "baseline_mean": mean_share,
                        "baseline_std": std_share,
                        "z_score": z_score,
                    }
                )
    return source_bias


def evaluate_pass_fail(
    summary: dict,
    completeness_rate: float,
    quarantine_rate: float,
    drift_checks: list[dict],
    source_bias: list[dict],
) -> bool:
    """Apply control thresholds to determine pass/fail."""
    if summary["n_events"] == 0:
        return False
    if summary["duplicate_rate"] > 0.01:
        return False
    if completeness_rate < COMPLETENESS_THRESHOLD:
        return False
    if quarantine_rate > QUARANTINE_RATE_THRESHOLD:
        return False
    if summary["future_events"] > 0:
        return False
    if any(check.get("drifted") for check in drift_checks):
        return False
    if source_bias:
        return False
    return True


def run(report_date: date | None = None) -> None:
    """Compute data quality report for a given report date."""
    if report_date is None:
        report_date = date.today() - timedelta(days=1)
    logger.info("dq_report_start", report_date=str(report_date))

    with engine.begin() as conn:
        totals = fetch_totals(conn, report_date)
        missing_required = fetch_missing_required(conn, report_date)
        completeness_rate = compute_completeness_rate(
            totals["n_events"], missing_required["total"]
        )
        freshness = fetch_freshness(conn, report_date)
        future = fetch_future_events(conn)
        quarantine = fetch_quarantine_stats(conn, report_date)
        quarantine_rate = (
            quarantine["quarantine_total"] / totals["n_events"]
            if totals["n_events"]
            else 0.0
        )
        keys = fetch_schema_keys(conn, report_date)
        drift_checks = fetch_distribution_drift(conn, report_date)
        source_bias = fetch_source_bias(conn, report_date)

        summary = {
            "date": str(report_date),
            "n_events": totals["n_events"],
            "duplicate_events": totals["duplicate_events"],
            "duplicate_rate": (
                totals["duplicate_events"] / totals["n_events"]
                if totals["n_events"]
                else 0.0
            ),
            "missing_required": missing_required,
            "malformed_events": quarantine["malformed_events"],
            "completeness_rate": completeness_rate,
            **freshness,
            "future_events": future,
            **quarantine,
            "quarantine_rate": quarantine_rate,
            "top_property_keys": keys,
            "distribution_drift": drift_checks,
            "source_bias": source_bias,
        }

        pass_ = evaluate_pass_fail(
            summary=summary,
            completeness_rate=completeness_rate,
            quarantine_rate=quarantine_rate,
            drift_checks=drift_checks,
            source_bias=source_bias,
        )

        summary["confidence"] = dq_confidence(
            n_events=totals["n_events"],
            completeness_rate=completeness_rate,
            quarantine_rate=quarantine_rate,
        )

        conn.execute(
            text("""
            INSERT INTO dq_reports(report_date, pass, summary)
            VALUES (CAST(:d AS date), :p, CAST(:s AS jsonb))
            ON CONFLICT (report_date) DO UPDATE
              SET pass = EXCLUDED.pass,
                  summary = EXCLUDED.summary,
                  computed_at = NOW()
            """),
            {"d": report_date, "p": pass_, "s": json.dumps(summary)},
        )
    logger.info("dq_report_complete", report_date=str(report_date), pass_=pass_)
