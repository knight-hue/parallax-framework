-- MySQL baseline: UTC DATETIME(6), explicit FK constraints, deterministic collation.
CREATE TABLE audit_run (
    id                VARCHAR(36) PRIMARY KEY,
    run_id            VARCHAR(64),
    credential_id VARCHAR(36) NOT NULL,
    repo_path         VARCHAR(1024),
    question          VARCHAR(2000),
    status            VARCHAR(24) NOT NULL,
    submitted_at      DATETIME(6) NOT NULL,
    finished_at       DATETIME(6),
    elapsed_s         DOUBLE,
    trace_id          VARCHAR(64),
    prompt_tokens     BIGINT,
    completion_tokens BIGINT,
    total_tokens      BIGINT,
    counts_json       VARCHAR(1024),
    stop_reason       VARCHAR(64),
    error             VARCHAR(2000),
    CONSTRAINT uq_audit_run_upstream UNIQUE (run_id),
    FOREIGN KEY (credential_id) REFERENCES api_credential(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE INDEX idx_audit_run_credential_submitted ON audit_run (credential_id, submitted_at);
CREATE INDEX idx_audit_run_status ON audit_run (status);
