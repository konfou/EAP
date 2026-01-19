## Development

### Quick Start

```bash
docker compose up --build
curl http://localhost:8000/health
```

### Docker Compose (DB + API + Dashboard)

```bash
docker compose up --build
```

Compose reads `.env` automatically; copy `.env.example` to `.env` for
local overrides.

To run scheduled jobs:

```bash
docker compose up --build scheduler
```

### Local venv + Docker DB

```bash
docker compose up -d db
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

To regenerate `requirements.txt` from `pyproject.toml`:

```bash
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt
```

### API

```bash
export DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/risk
eap-api
```

### Dashboard

```bash
export DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/risk
eap-dashboard
```

## Workflow

### 1. Startup

```bash
docker compose up --build
curl http://localhost:8000/health
```

### 2. Ingestion

```bash
curl -X POST http://localhost:8000/ingest/events \
  -H "Content-Type: application/json" \
  -H "X-Role: operator" \
  -d '{
    "events": [
      {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "ts_event": "2026-01-13T10:00:00Z",
        "event_type": "transaction_completed",
        "source_system": "payments",
        "user_id": "user_1",
        "value": 120.50,
        "measurement_uncertainty": 0.5,
        "properties": {"currency": "EUR"}
      }
    ]
  }'
```

Example response:

```json
{ "accepted": 1, "rejected": 0, "rejected_reasons": {} }
```

#### Idempotency & Quarantine

```bash
curl -X POST http://localhost:8000/ingest/events \
  -H "Content-Type: application/json" \
  -H "X-Role: operator" \
  -d '{
    "events": [
      {
        "event_id": "11111111-1111-1111-1111-111111111111",
        "ts_event": "2026-01-13T10:00:00Z",
        "event_type": "transaction_completed",
        "source_system": "payments",
        "value": 120.5
      }
    ]
  }'
```

Example response:

```json
{
  "accepted": 0,
  "rejected": 1,
  "rejected_reasons": { "duplicate_event_id": 1 }
}
```

### 3. Controls (DQ)

```bash
docker compose exec api python -m jobs.dq
curl http://localhost:8000/dq/latest
```

Local alternative:

```bash
eap-job-dq
```

Example response:

```json
{
  "report_date": "2026-01-13",
  "pass": true,
  "summary": {
    "n_events": 3,
    "duplicate_events": 0,
    "duplicate_rate": 0.0,
    "confidence": 0.42
  }
}
```

### 4. Metrics

```bash
docker compose exec api python -m jobs.metrics
curl "http://localhost:8000/metrics/daily?metric=tx_fail_rate&date_from=2026-01-13&date_to=2026-01-13"
```

Local alternative:

```bash
eap-job-metrics
```

Example response:

```json
[
  {
    "metric_date": "2026-01-13",
    "metric_name": "tx_fail_rate",
    "value": 0.25,
    "dimensions": {}
  }
]
```

### 5. Anomalies

```bash
docker compose exec api python -m jobs.anomaly
```

Local alternative:

```bash
eap-job-anomaly
```

### 6. Alerts

```bash
curl http://localhost:8000/alerts/recent
curl -X POST http://localhost:8000/alerts/1/ack \
  -H "Content-Type: application/json" \
  -H "X-Role: operator" \
  -d '{"actor": "ops-user"}'
```

Example response:

```json
[
  {
    "alert_id": 1,
    "metric_name": "tx_fail_rate",
    "severity": "WARN",
    "rule_version": "2025-01-15",
    "risk_score": 12.3,
    "status": "OPEN"
  }
]
```

### 7. Notifications

Configure notification targets:

```bash
export ALERT_EMAIL_TO=ops@example.com
export ALERT_WEBHOOK_URLS=https://hooks.example.com/alerts
```

Trigger routing:

```bash
eap-job-notify
```

### 8. Tests

```bash
pytest -v
```

### 9. CI

CI runs unit/integration tests plus Docker builds via `.github/workflows/ci.yml`:

```bash
pytest -v
docker build -t eap-api -f Dockerfile .
docker build -t eap-dashboard -f Dockerfile.dashboard .
```

## Example (From README)

- Ingest spike → Metrics compute elevated failure rate → Anomaly detection flags.
- z-score + EWMA → Alert converts to risk score → Executive review.

1. Seed 7 days of baseline (low failure rate)

```bash
for day in 06 07 08 09 10 11 12; do
  curl -s -X POST http://localhost:8000/ingest/events \
    -H "Content-Type: application/json" \
    -H "X-Role: operator" \
    -d @- >/dev/null <<JSON
{
  "events": [
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-${day}T10:00:00Z",
      "event_type": "transaction_completed",
      "source_system": "payments",
      "user_id": "u1",
      "value": 120.5,
      "measurement_uncertainty": 0.5
    },
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-${day}T10:05:00Z",
      "event_type": "transaction_failed",
      "source_system": "payments",
      "user_id": "u2",
      "value": 0
    }
  ]
}
JSON
done
```

2. Create spike day with heavy failures (2026-01-13)

```bash
curl -s -X POST http://localhost:8000/ingest/events \
  -H "Content-Type: application/json" \
  -H "X-Role: operator" \
  -d @- >/dev/null <<JSON
{
  "events": [
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-13T10:00:00Z",
      "event_type": "transaction_completed",
      "source_system": "payments",
      "user_id": "u1",
      "value": 120.5
    },
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-13T10:05:00Z",
      "event_type": "transaction_failed",
      "source_system": "payments",
      "user_id": "u2",
      "value": 0
    },
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-13T10:06:00Z",
      "event_type": "transaction_failed",
      "source_system": "payments",
      "user_id": "u3",
      "value": 0
    },
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-13T10:07:00Z",
      "event_type": "transaction_failed",
      "source_system": "payments",
      "user_id": "u4",
      "value": 0
    },
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-13T10:08:00Z",
      "event_type": "transaction_failed",
      "source_system": "payments",
      "user_id": "u5",
      "value": 0
    },
    {
      "event_id": "$(uuidgen)",
      "ts_event": "2026-01-13T10:09:00Z",
      "event_type": "transaction_failed",
      "source_system": "payments",
      "user_id": "u6",
      "value": 0
    }
  ]
}
JSON
```

3. Recompute metrics and run anomaly detection on spike day

```bash
docker compose exec api python -m jobs.metrics --start 2026-01-06 --end 2026-01-13
docker compose exec -T api python -c "from datetime import date; from jobs.anomaly import run; run(date(2026, 1, 13))"
```

Local alternative:

```bash
eap-job-metrics --start 2026-01-06 --end 2026-01-13
python -c "from datetime import date; from jobs.anomaly import run; run(date(2026, 1, 13))"
```

4. Review alerts

```bash
curl http://localhost:8000/alerts/recent
```

Example response:

```json
[
  {
    "alert_id": 1,
    "ts": "2026-01-13T10:15:00Z",
    "metric_name": "tx_fail_rate",
    "metric_date": "2026-01-13",
    "severity": "WARN",
    "rule_version": "2025-01-15",
    "risk_score": 12.3,
    "message": "tx_fail_rate anomalous on 2026-01-13",
    "context": { "method": "z_score" },
    "status": "OPEN",
    "acked_by": null,
    "acked_at": null,
    "resolved_by": null,
    "resolved_at": null
  }
]
```
