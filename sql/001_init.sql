CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Append-only immutable raw events (audit trail)
CREATE TABLE IF NOT EXISTS events_raw (
  event_id UUID PRIMARY KEY,
  ts_event TIMESTAMPTZ NOT NULL,
  ts_ingested TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  event_type TEXT NOT NULL,
  source_system TEXT NOT NULL,
  user_id TEXT,
  value DOUBLE PRECISION,
  measurement_uncertainty DOUBLE PRECISION,
  properties JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE OR REPLACE FUNCTION prevent_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'events_raw is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS events_raw_no_update ON events_raw;
DROP TRIGGER IF EXISTS events_raw_no_delete ON events_raw;

CREATE TRIGGER events_raw_no_update
BEFORE UPDATE ON events_raw
FOR EACH STATEMENT EXECUTE FUNCTION prevent_mutation();

CREATE TRIGGER events_raw_no_delete
BEFORE DELETE ON events_raw
FOR EACH STATEMENT EXECUTE FUNCTION prevent_mutation();

CREATE INDEX IF NOT EXISTS idx_events_raw_ts_event ON events_raw (ts_event);
CREATE INDEX IF NOT EXISTS idx_events_raw_type_ts ON events_raw (event_type, ts_event);
CREATE INDEX IF NOT EXISTS idx_events_raw_source_ts ON events_raw (source_system, ts_event);

-- 2) Quarantine for invalid events (controls / explainability)
CREATE TABLE IF NOT EXISTS events_quarantine (
  quarantine_id BIGSERIAL PRIMARY KEY,
  ts_ingested TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reason TEXT NOT NULL,
  raw_payload JSONB NOT NULL
);

CREATE OR REPLACE FUNCTION prevent_quarantine_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'events_quarantine is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS events_quarantine_no_update ON events_quarantine;
DROP TRIGGER IF EXISTS events_quarantine_no_delete ON events_quarantine;

CREATE TRIGGER events_quarantine_no_update
BEFORE UPDATE ON events_quarantine
FOR EACH STATEMENT EXECUTE FUNCTION prevent_quarantine_mutation();

CREATE TRIGGER events_quarantine_no_delete
BEFORE DELETE ON events_quarantine
FOR EACH STATEMENT EXECUTE FUNCTION prevent_quarantine_mutation();

-- 3) Daily metrics (batch derived)
CREATE TABLE IF NOT EXISTS metrics_daily (
  metric_date DATE NOT NULL,
  metric_name TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  dimensions JSONB NOT NULL DEFAULT '{}'::jsonb,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (metric_date, metric_name, dimensions)
);

-- 4) Data quality reports (daily controls)
CREATE TABLE IF NOT EXISTS dq_reports (
  report_date DATE PRIMARY KEY,
  pass BOOLEAN NOT NULL,
  summary JSONB NOT NULL,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5) Alerts (anomaly/risk events)
CREATE TABLE IF NOT EXISTS alerts (
  alert_id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metric_name TEXT NOT NULL,
  metric_date DATE,
  severity TEXT NOT NULL,          -- INFO/WARN/CRITICAL
  rule_version TEXT NOT NULL DEFAULT 'v1',
  risk_score DOUBLE PRECISION NOT NULL,
  message TEXT NOT NULL,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN/ACK/RESOLVED
  acked_by TEXT,
  acked_at TIMESTAMPTZ,
  resolved_by TEXT,
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS alert_notifications (
  notification_id BIGSERIAL PRIMARY KEY,
  alert_id BIGINT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
  channel TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  last_error TEXT,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (alert_id, channel, target)
);

CREATE TABLE IF NOT EXISTS audit_log (
  audit_id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS anomaly_rules (
  rule_name TEXT PRIMARY KEY,
  rule_version TEXT NOT NULL,
  config JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO anomaly_rules(rule_name, rule_version, config)
VALUES (
  'anomaly_rules',
  'v1',
  '{"ewma_lambda":0.3,"ewma_limit":3,"change_point_window":7,"change_point_z":3,"seasonal_min_points":3,"seasonal_z":3,"regime_recent_days":7,"regime_baseline_days":14,"regime_z":3,"regime_var_ratio":2}'::jsonb
)
ON CONFLICT (rule_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS api_metrics (
  id INT PRIMARY KEY DEFAULT 1,
  total_requests BIGINT NOT NULL DEFAULT 0,
  total_errors BIGINT NOT NULL DEFAULT 0,
  total_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts (ts DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alert_notifications_alert ON alert_notifications (alert_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log (ts DESC);
