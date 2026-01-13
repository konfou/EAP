# Enterprise Analytics Platform (EAP)

Python | FastAPI | PostgreSQL | Statistical Controls

## Executive Summary

This project implements a production-style enterprise analytics platform
designed to detect operational, financial, and data quality risks in
high-volume event data. The platform ingests raw operational events,
validates data integrity, computes business-critical metrics, detects
statistically significant anomalies, and translates those anomalies into
quantified risk scores suitable for executive and risk stakeholders.
The system applies measurement theory and statistical controls to ensure
accuracy and auditability rather than opaque "black-box" analytics.

## Business Problem

Modern enterprises depend on event data (transactions, system
performance, user activity) to make operational and financial decisions.

However:

- Data quality failures introduce hidden risk.
- Metric deviations are often detected too late.
- Black-box models are difficult to audit.

The platform addresses these gaps by applying a physics-influenced
measurement mindset.

## Measurement & Risk Philosophy (Physics Lens)

Enterprise events are treated as measured signals rather than raw facts.
Each signal carries uncertainty, drift, and latency just like physical
instruments. Calibration checks, control charts, and confidence scoring
ensure risk insights are grounded in measurement theory.

## Validation & Controls

Daily data quality reports quantify completeness, duplication, latency,
schema drift, and source bias. These checks establish whether the
measurement system is "in calibration" before downstream analytics are
trusted.

## Solution Overview

The system is built around five core principles:

1. **Immutable measurement records**
   Raw events are stored append-only to preserve auditability and enable
   forensic analysis.

2. **Automated data quality controls**
   Daily validation checks quantify completeness, duplication,
   freshness, and schema drift.

3. **Reproducible business metrics**
   Key KPIs (failure rates, latency, volume, DAU) are computed in
   deterministic batch jobs.

4. **Explainable statistical anomaly detection**
   Control-chart-style methods (rolling baselines, z-scores, persistence
   checks) identify abnormal behavior with confidence levels.

5. **Risk translation**
   Anomalies converted into risk scores combining impact, confidence,
   and persistence; bridging technical signals to business risk.

## System Architecture

- Ingestion API (FastAPI): Validates and records events with idempotency
  guarantees.
- PostgreSQL: Immutable raw events, quarantined failures, derived
  metrics, alerts.
- Batch Jobs (Python):
  - Data Quality
  - Metrics
  - Anomaly Detection
- Metrics & Alerts API: Serves executive-ready outputs.
- CI Pipeline: Automated testing with real database integration.

## Example Incident Walkthrough

1. A sudden spike in `tx_fail_rate` is ingested.
2. Metrics compute the elevated failure rate for the day.
3. Anomaly detection flags a high z-score with EWMA confirmation.
4. The alert is translated into a risk score with severity and context.
5. Executives review the risk signal alongside confidence and impact.

## Concluding Notes

### Key Features

- Event-level idempotency and quarantine for invalid data.
- Daily data quality scorecards with pass/fail controls.
- Explainable anomaly detection (no black-box ML).
- Quantified risk scoring framework.
- Full test coverage for ingestion, controls, and APIs.
- GitHub Actions CI with Postgres-backed integration tests.

### Intended Use Cases

- Operational risk monitoring.
- Transaction failure analysis.
- SLA and performance governance.
- Internal audit analytics.
- Data quality assurance for regulated environments.

### Limitations & Next Steps

- Statistical thresholds are heuristics; tune per business domain.
- Seasonality and regime detection can be refined with richer models.
- Extend controls to cover additional metrics and domain-specific KPIs.

## Docs

- See `USAGE.md` for development and workflow guide.
- AI-assisted development is used on this project; see `AGENTS.md` for
  guidelines.
