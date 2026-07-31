CREATE TABLE IF NOT EXISTS logs (
    id         TEXT PRIMARY KEY,
    timestamp  TIMESTAMPTZ NOT NULL,
    service    TEXT NOT NULL,
    severity   TEXT NOT NULL,
    message    TEXT NOT NULL,
    metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_logs_service_timestamp
    ON logs (service, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_logs_severity_timestamp
    ON logs (severity, timestamp DESC);