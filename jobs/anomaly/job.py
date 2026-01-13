"""Explainable statistical anomaly detection with risk translation."""

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

EWMA_LAMBDA = 0.3
EWMA_LIMIT = 3.0
CHANGE_POINT_WINDOW = 7
CHANGE_POINT_Z = 3.0
SEASONAL_MIN_POINTS = 3
SEASONAL_Z = 3.0
REGIME_RECENT_DAYS = 7
REGIME_BASELINE_DAYS = 14
REGIME_Z = 3.0
REGIME_VAR_RATIO = 2.0


def zscore(value: float, mean: float, std_dev: float) -> float:
    """Compute z-score safely for near-zero variance."""
    if std_dev <= 1e-9:
        return 0.0
    return (value - mean) / std_dev


def severity_from_z(z_score: float) -> str:
    """Map z-score to alert severity bands."""
    abs_z = abs(z_score)
    if abs_z >= 4:
        return "CRITICAL"
    if abs_z >= 3:
        return "WARN"
    if abs_z >= 2:
        return "INFO"
    return "INFO"


def risk_score(impact: float, confidence: float, persistence: float) -> float:
    """Compute bounded risk score from three factors."""
    return float(max(0.0, impact) * max(0.0, confidence) * max(0.0, persistence))


def impact_from_metric(
    metric_name: str, observed: float, baseline_mean: float
) -> float:
    """Translate metric deviation into business impact."""
    if metric_name == "tx_fail_rate":
        return max(0.0, observed - baseline_mean) * 100.0
    if metric_name == "latency_p95_ms":
        return max(0.0, observed - baseline_mean) / 100.0
    if metric_name == "tx_completed":
        return max(0.0, (baseline_mean - observed) / max(1.0, baseline_mean)) * 10.0
    return max(0.0, (baseline_mean - observed) / max(1.0, baseline_mean)) * 5.0


def load_rule_config(conn) -> dict:
    try:
        row = (
            conn.execute(
                text(
                    """
            SELECT rule_version, config
            FROM anomaly_rules
            WHERE rule_name = 'anomaly_rules'
            ORDER BY updated_at DESC
            LIMIT 1
            """
                )
            )
            .mappings()
            .first()
        )
        if row:
            config = row["config"] or {}
            return {
                "rule_version": row["rule_version"],
                "ewma_lambda": float(config.get("ewma_lambda", EWMA_LAMBDA)),
                "ewma_limit": float(config.get("ewma_limit", EWMA_LIMIT)),
                "change_point_window": int(
                    config.get("change_point_window", CHANGE_POINT_WINDOW)
                ),
                "change_point_z": float(config.get("change_point_z", CHANGE_POINT_Z)),
                "seasonal_min_points": int(
                    config.get("seasonal_min_points", SEASONAL_MIN_POINTS)
                ),
                "seasonal_z": float(config.get("seasonal_z", SEASONAL_Z)),
                "regime_recent_days": int(
                    config.get("regime_recent_days", REGIME_RECENT_DAYS)
                ),
                "regime_baseline_days": int(
                    config.get("regime_baseline_days", REGIME_BASELINE_DAYS)
                ),
                "regime_z": float(config.get("regime_z", REGIME_Z)),
                "regime_var_ratio": float(
                    config.get("regime_var_ratio", REGIME_VAR_RATIO)
                ),
            }
    except Exception:
        return {
            "rule_version": "v1",
            "ewma_lambda": EWMA_LAMBDA,
            "ewma_limit": EWMA_LIMIT,
            "change_point_window": CHANGE_POINT_WINDOW,
            "change_point_z": CHANGE_POINT_Z,
            "seasonal_min_points": SEASONAL_MIN_POINTS,
            "seasonal_z": SEASONAL_Z,
            "regime_recent_days": REGIME_RECENT_DAYS,
            "regime_baseline_days": REGIME_BASELINE_DAYS,
            "regime_z": REGIME_Z,
            "regime_var_ratio": REGIME_VAR_RATIO,
        }
    return {
        "rule_version": "v1",
        "ewma_lambda": EWMA_LAMBDA,
        "ewma_limit": EWMA_LIMIT,
        "change_point_window": CHANGE_POINT_WINDOW,
        "change_point_z": CHANGE_POINT_Z,
        "seasonal_min_points": SEASONAL_MIN_POINTS,
        "seasonal_z": SEASONAL_Z,
        "regime_recent_days": REGIME_RECENT_DAYS,
        "regime_baseline_days": REGIME_BASELINE_DAYS,
        "regime_z": REGIME_Z,
        "regime_var_ratio": REGIME_VAR_RATIO,
    }


def insert_alert(
    conn,
    metric_name: str,
    metric_date: date,
    severity: str,
    rule_version: str,
    risk_score_value: float,
    message: str,
    context: dict,
) -> None:
    """Persist alert with structured context payload."""
    conn.execute(
        text(
            """
      INSERT INTO alerts(metric_name, metric_date, severity, rule_version, risk_score, message, context)
      VALUES (:m, CAST(:d AS date), :sev, :rule_version, :rs, :msg, CAST(:ctx AS jsonb))
    """
        ),
        {
            "m": metric_name,
            "d": metric_date,
            "sev": severity,
            "rule_version": rule_version,
            "rs": risk_score_value,
            "msg": message,
            "ctx": json.dumps(context),
        },
    )


def fetch_series(
    conn, metric_name: str, target_date: date, lookback_days: int = 30
) -> list[dict]:
    """Load time series for a metric over the lookback window."""
    return (
        conn.execute(
            text(
                """
        SELECT metric_date, value
        FROM metrics_daily
        WHERE metric_name=:m
          AND metric_date >= CAST(:d0 AS date)
          AND metric_date <= CAST(:d1 AS date)
        ORDER BY metric_date ASC
    """
            ),
            {
                "m": metric_name,
                "d0": target_date - timedelta(days=lookback_days),
                "d1": target_date,
            },
        )
        .mappings()
        .all()
    )


def build_series(series_rows: list[dict]) -> tuple[dict[date, float], list[float]]:
    """Build date->value map and raw value list."""
    series_by_date = {row["metric_date"]: float(row["value"]) for row in series_rows}
    series_values = [float(row["value"]) for row in series_rows]
    return series_by_date, series_values


def compute_baseline(series_rows: list[dict], target_date: date) -> list[float]:
    """Return baseline window values for rolling comparisons."""
    return [
        float(row["value"])
        for row in series_rows
        if target_date - timedelta(days=7)
        <= row["metric_date"]
        <= target_date - timedelta(days=1)
    ]


def compute_persistence(
    series_by_date: dict[date, float],
    target_date: date,
    baseline_mean: float,
    baseline_std: float,
) -> float:
    """Boost persistence when consecutive days deviate."""
    previous_value = series_by_date.get(target_date - timedelta(days=1))
    persistence = 1.0
    if previous_value is not None and baseline_std > 0:
        previous_z = zscore(float(previous_value), baseline_mean, baseline_std)
        if (previous_z > 2) or (previous_z < -2):
            persistence = 1.3
    return persistence


def maybe_insert_zscore_alert(
    conn,
    metric_name: str,
    target_date: date,
    observed: float,
    baseline_vals: list[float],
    baseline_mean: float,
    baseline_std: float,
    persistence: float,
    rule_version: str,
) -> None:
    """Flag deviations using a rolling z-score control."""
    z_score = zscore(observed, baseline_mean, baseline_std)
    if abs(z_score) < 3:
        return
    impact = impact_from_metric(metric_name, observed, baseline_mean)
    confidence = min(1.0, abs(z_score) / 5.0)
    rs = risk_score(impact=impact, confidence=confidence, persistence=persistence)
    msg = (
        f"{metric_name} anomalous on {target_date}: observed={observed:.4g}, "
        f"baseline_mean={baseline_mean:.4g}, z={z_score:.2f}"
    )
    ctx = {
        "method": "z_score",
        "observed": observed,
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "z_score": z_score,
        "impact": impact,
        "confidence": confidence,
        "persistence": persistence,
        "baseline_window_days": len(baseline_vals),
    }
    insert_alert(
        conn,
        metric_name=metric_name,
        metric_date=target_date,
        severity=severity_from_z(z_score),
        rule_version=rule_version,
        risk_score_value=rs,
        message=msg,
        context=ctx,
    )


def maybe_insert_ewma_alert(
    conn,
    metric_name: str,
    target_date: date,
    observed: float,
    baseline_vals: list[float],
    baseline_mean: float,
    baseline_std: float,
    persistence: float,
    rule_version: str,
    ewma_lambda: float,
    ewma_limit: float,
) -> None:
    """Flag deviations using EWMA control charts."""
    if baseline_std <= 0 or len(baseline_vals) < 2:
        return
    ewma_prev = baseline_vals[0]
    for val in baseline_vals[1:]:
        ewma_prev = ewma_lambda * val + (1 - ewma_lambda) * ewma_prev
    ewma_current = ewma_lambda * observed + (1 - ewma_lambda) * ewma_prev
    ewma_sigma = baseline_std * math.sqrt(ewma_lambda / (2 - ewma_lambda))
    if ewma_sigma <= 0:
        return
    ewma_z = (ewma_current - baseline_mean) / ewma_sigma
    if abs(ewma_z) < ewma_limit:
        return
    impact = impact_from_metric(metric_name, observed, baseline_mean)
    confidence = min(1.0, abs(ewma_z) / 5.0)
    rs = risk_score(impact=impact, confidence=confidence, persistence=persistence)
    msg = (
        f"{metric_name} EWMA signal on {target_date}: observed={observed:.4g}, "
        f"ewma={ewma_current:.4g}, z={ewma_z:.2f}"
    )
    ctx = {
        "method": "ewma",
        "observed": observed,
        "ewma": ewma_current,
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "ewma_z": ewma_z,
        "impact": impact,
        "confidence": confidence,
        "persistence": persistence,
    }
    insert_alert(
        conn,
        metric_name=metric_name,
        metric_date=target_date,
        severity=severity_from_z(ewma_z),
        rule_version=rule_version,
        risk_score_value=rs,
        message=msg,
        context=ctx,
    )


def maybe_insert_change_point_alert(
    conn,
    metric_name: str,
    target_date: date,
    observed: float,
    series_values: list[float],
    baseline_mean: float,
    persistence: float,
    rule_version: str,
    window: int,
    threshold: float,
) -> None:
    """Flag level shifts using a two-window change-point test."""
    if len(series_values) < 2 * window:
        return
    recent_vals = series_values[-window:]
    prev_vals = series_values[-2 * window : -window]
    if len(recent_vals) != len(prev_vals) or len(recent_vals) <= 1:
        return
    recent_mean = float(np.mean(recent_vals))
    prev_mean = float(np.mean(prev_vals))
    recent_var = float(np.var(recent_vals, ddof=1))
    prev_var = float(np.var(prev_vals, ddof=1))
    pooled_var = (
        (len(recent_vals) - 1) * recent_var + (len(prev_vals) - 1) * prev_var
    ) / (len(recent_vals) + len(prev_vals) - 2)
    pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 0.0
    if pooled_std <= 0:
        return
    cp_z = (recent_mean - prev_mean) / (pooled_std * math.sqrt(2 / len(recent_vals)))
    if abs(cp_z) < threshold:
        return
    impact = impact_from_metric(metric_name, observed, baseline_mean)
    confidence = min(1.0, abs(cp_z) / 5.0)
    rs = risk_score(impact=impact, confidence=confidence, persistence=persistence)
    msg = (
        f"{metric_name} change-point on {target_date}: "
        f"prev_mean={prev_mean:.4g}, recent_mean={recent_mean:.4g}"
    )
    ctx = {
        "method": "change_point",
        "observed": observed,
        "previous_mean": prev_mean,
        "recent_mean": recent_mean,
        "change_point_z": cp_z,
        "impact": impact,
        "confidence": confidence,
        "persistence": persistence,
        "window": window,
    }
    insert_alert(
        conn,
        metric_name=metric_name,
        metric_date=target_date,
        severity=severity_from_z(cp_z),
        rule_version=rule_version,
        risk_score_value=rs,
        message=msg,
        context=ctx,
    )


def maybe_insert_seasonal_alert(
    conn,
    metric_name: str,
    target_date: date,
    observed: float,
    series_rows: list[dict],
    baseline_mean: float,
    persistence: float,
    rule_version: str,
    min_points: int,
    threshold: float,
) -> None:
    """Flag seasonal deviations using weekday baselines."""
    seasonal_vals = [
        float(row["value"])
        for row in series_rows
        if row["metric_date"] < target_date
        and row["metric_date"].weekday() == target_date.weekday()
    ]
    seasonal_vals = seasonal_vals[-4:]
    if len(seasonal_vals) < min_points:
        return
    seasonal_mean = float(np.mean(seasonal_vals))
    seasonal_std = (
        float(np.std(seasonal_vals, ddof=1)) if len(seasonal_vals) > 1 else 0.0
    )
    if seasonal_std <= 0:
        return
    seasonal_z = (observed - seasonal_mean) / seasonal_std
    if abs(seasonal_z) < threshold:
        return
    impact = impact_from_metric(metric_name, observed, seasonal_mean)
    confidence = min(1.0, abs(seasonal_z) / 5.0)
    rs = risk_score(impact=impact, confidence=confidence, persistence=persistence)
    msg = (
        f"{metric_name} seasonal deviation on {target_date}: "
        f"observed={observed:.4g}, seasonal_mean={seasonal_mean:.4g}"
    )
    ctx = {
        "method": "seasonal_decomposition",
        "observed": observed,
        "seasonal_mean": seasonal_mean,
        "seasonal_std": seasonal_std,
        "seasonal_z": seasonal_z,
        "impact": impact,
        "confidence": confidence,
        "persistence": persistence,
    }
    insert_alert(
        conn,
        metric_name=metric_name,
        metric_date=target_date,
        severity=severity_from_z(seasonal_z),
        rule_version=rule_version,
        risk_score_value=rs,
        message=msg,
        context=ctx,
    )


def maybe_insert_regime_shift_alert(
    conn,
    metric_name: str,
    target_date: date,
    observed: float,
    series_values: list[float],
    persistence: float,
    rule_version: str,
    recent_days: int,
    baseline_days: int,
    threshold: float,
    var_ratio_threshold: float,
) -> None:
    """Flag sustained mean/variance shifts across regimes."""
    if len(series_values) < recent_days + baseline_days:
        return
    recent_vals = series_values[-recent_days:]
    prior_vals = series_values[-(recent_days + baseline_days) : -recent_days]
    if len(prior_vals) < 2 or len(recent_vals) < 2:
        return
    prior_mean = float(np.mean(prior_vals))
    prior_std = float(np.std(prior_vals, ddof=1))
    recent_mean = float(np.mean(recent_vals))
    recent_var = float(np.var(recent_vals, ddof=1))
    prior_var = float(np.var(prior_vals, ddof=1))
    mean_z = (
        (recent_mean - prior_mean) / (prior_std / math.sqrt(len(recent_vals)))
        if prior_std > 0
        else 0.0
    )
    var_ratio = recent_var / prior_var if prior_var > 0 else float("inf")
    if (
        abs(mean_z) < threshold
        and var_ratio < var_ratio_threshold
        and var_ratio > 1 / var_ratio_threshold
    ):
        return
    impact = impact_from_metric(metric_name, observed, prior_mean)
    confidence = min(1.0, abs(mean_z) / 5.0)
    rs = risk_score(impact=impact, confidence=confidence, persistence=persistence)
    msg = (
        f"{metric_name} regime shift on {target_date}: "
        f"prior_mean={prior_mean:.4g}, recent_mean={recent_mean:.4g}"
    )
    ctx = {
        "method": "regime_shift",
        "observed": observed,
        "prior_mean": prior_mean,
        "recent_mean": recent_mean,
        "mean_z": mean_z,
        "prior_var": prior_var,
        "recent_var": recent_var,
        "var_ratio": var_ratio,
        "impact": impact,
        "confidence": confidence,
        "persistence": persistence,
    }
    insert_alert(
        conn,
        metric_name=metric_name,
        metric_date=target_date,
        severity=severity_from_z(mean_z),
        rule_version=rule_version,
        risk_score_value=rs,
        message=msg,
        context=ctx,
    )


def run(target_date: date | None = None) -> None:
    """Run anomaly detection suite for a target date."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    logger.info("anomaly_run_start", target_date=str(target_date))

    metrics = ["tx_fail_rate", "latency_p95_ms", "tx_completed", "dau"]

    with engine.begin() as conn:
        rule_config = load_rule_config(conn)
        rule_version = rule_config["rule_version"]
        for metric_name in metrics:
            series_rows = fetch_series(conn, metric_name, target_date)
            if len(series_rows) < 6:
                continue

            series_by_date, series_values = build_series(series_rows)
            observed = series_by_date.get(target_date)
            if observed is None:
                continue

            baseline_vals = compute_baseline(series_rows, target_date)
            if len(baseline_vals) < 5:
                continue

            baseline_mean = float(np.mean(baseline_vals))
            baseline_std = (
                float(np.std(baseline_vals, ddof=1)) if len(baseline_vals) > 1 else 0.0
            )
            persistence = compute_persistence(
                series_by_date, target_date, baseline_mean, baseline_std
            )

            maybe_insert_zscore_alert(
                conn,
                metric_name=metric_name,
                target_date=target_date,
                observed=observed,
                baseline_vals=baseline_vals,
                baseline_mean=baseline_mean,
                baseline_std=baseline_std,
                persistence=persistence,
                rule_version=rule_version,
            )
            maybe_insert_ewma_alert(
                conn,
                metric_name=metric_name,
                target_date=target_date,
                observed=observed,
                baseline_vals=baseline_vals,
                baseline_mean=baseline_mean,
                baseline_std=baseline_std,
                persistence=persistence,
                rule_version=rule_version,
                ewma_lambda=rule_config["ewma_lambda"],
                ewma_limit=rule_config["ewma_limit"],
            )
            maybe_insert_change_point_alert(
                conn,
                metric_name=metric_name,
                target_date=target_date,
                observed=observed,
                series_values=series_values,
                baseline_mean=baseline_mean,
                persistence=persistence,
                rule_version=rule_version,
                window=rule_config["change_point_window"],
                threshold=rule_config["change_point_z"],
            )
            maybe_insert_seasonal_alert(
                conn,
                metric_name=metric_name,
                target_date=target_date,
                observed=observed,
                series_rows=series_rows,
                baseline_mean=baseline_mean,
                persistence=persistence,
                rule_version=rule_version,
                min_points=rule_config["seasonal_min_points"],
                threshold=rule_config["seasonal_z"],
            )
            maybe_insert_regime_shift_alert(
                conn,
                metric_name=metric_name,
                target_date=target_date,
                observed=observed,
                series_values=series_values,
                persistence=persistence,
                rule_version=rule_version,
                recent_days=rule_config["regime_recent_days"],
                baseline_days=rule_config["regime_baseline_days"],
                threshold=rule_config["regime_z"],
                var_ratio_threshold=rule_config["regime_var_ratio"],
            )
    logger.info("anomaly_run_complete", target_date=str(target_date))
