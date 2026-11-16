-- MySQL baseline: UTC TIMESTAMP(6), explicit FK constraints, deterministic collation.
CREATE TABLE audit_event (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id     VARCHAR(64) NOT NULL,
    event_type VARCHAR(48) NOT NULL,
    at         TIMESTAMP(6) NOT NULL,
    detail     VARCHAR(1024),
    trace_id   VARCHAR(64)
);

CREATE INDEX idx_audit_event_run ON audit_event (run_id, at);
