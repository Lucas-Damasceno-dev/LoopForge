CREATE TABLE IF NOT EXISTS import_batch (
    id BIGSERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    imported_at TIMESTAMP WITH TIME ZONE NOT NULL,
    row_count INTEGER NOT NULL,
    issue_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_issue (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT NOT NULL,
    line_number INTEGER NOT NULL,
    column_name VARCHAR(255),
    severity VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL,
    message VARCHAR(2000) NOT NULL,
    suggestion VARCHAR(1000)
);

CREATE TABLE IF NOT EXISTS validation_issue_related_lines (
    validation_issue_id BIGINT NOT NULL,
    related_lines INTEGER,
    CONSTRAINT fk_validation_issue_related_lines
        FOREIGN KEY (validation_issue_id) REFERENCES validation_issue(id)
);

CREATE TABLE IF NOT EXISTS reference_registry (
    id BIGSERIAL PRIMARY KEY,
    reference_type VARCHAR(100) NOT NULL,
    reference_value VARCHAR(255) NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uk_reference_registry_type_value
    ON reference_registry(reference_type, reference_value);