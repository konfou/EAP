# Batch analytics (Literate guide)

This directory contains the offline analytics workflows that translate
the platform's physics-inspired principles into executable jobs. Each
job is intentionally broken into small, named functions so the reasoning
behind every KPI and control is visible and testable.

## How this maps to the platform principles

1. **Immutable measurement records**
   The jobs only read `events_raw` and `events_quarantine`, preserving the
   append-only audit trail defined in `sql/001_init.sql`.

2. **Automated data quality controls**
   `jobs.dq.job` evaluates completeness, freshness, drift, and bias to ensure
   "instrument validation" before any metric is trusted.

3. **Reproducible business metrics**
   `jobs.metrics.job` produces deterministic daily KPIs (failure rate,
   latency, volume, DAU).

4. **Explainable statistical anomaly detection**
   `jobs.anomaly.job` uses transparent statistics (z-score, EWMA, change-point,
   seasonal, and regime-shift checks) instead of opaque ML.

5. **Risk translation**
   Alerts multiply impact, confidence, and persistence into a risk score,
   bridging technical signals to business risk.

## `jobs.dq.job` — Data quality as experimental validation

Physics framing: treat the event stream as a measured signal. The job checks
whether the "instrument" is calibrated and stable.

### Key building blocks:

- **Completeness:** `fetch_missing_required` and
  `compute_completeness_rate` quantify missing required measurements.
- **Malformed Events:** `fetch_quarantine_stats` counts quarantined payloads
  (distinct from duplicate idempotency errors).
- **Freshness & Latency:** `fetch_freshness` tracks p50/p95 ingestion lag.
- **Distribution Drift:** `fetch_distribution_drift` uses a KS test to
  compare today’s values against the prior week for core event types.
- **Source Bias:** `fetch_source_bias` compares source share shifts against
  the last 7 days, flagging statistically unusual changes.
- **Confidence:** `dq_confidence` blends volume, completeness, and
  cleanliness into a report confidence score.

The summary is written to `dq_reports` with explicit pass/fail logic in
`evaluate_pass_fail`.

## `jobs.metrics.job` — Reproducible KPIs

Physics framing: deterministic, repeatable measurements.

Each KPI lives in its own function so it can be inspected and tested:

- **Failure rate:** `fetch_tx_fail_rate`
- **Latency p95:** `fetch_latency_p95`
- **Transaction volume/value:** `fetch_tx_completed`
- **DAU:** `fetch_dau`

All metrics are upserted through `upsert_metric` for idempotent reruns.

## `jobs.anomaly.job` — Explainable statistical controls

Physics framing: control-chart thinking with explicit thresholds.

The job builds a daily series and then applies named detection methods:

- **Z-score:** `maybe_insert_zscore_alert`
- **EWMA control chart:** `maybe_insert_ewma_alert`
- **Change-point detection:** `maybe_insert_change_point_alert`
- **Seasonal deviation:** `maybe_insert_seasonal_alert`
- **Regime shift:** `maybe_insert_regime_shift_alert`

Each method computes a confidence score and contributes a context
payload explaining the deviation. `impact_from_metric` maps technical
deviations to business impact and `risk_score` translates that into a
risk signal.
