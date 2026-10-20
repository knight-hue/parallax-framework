-- MySQL baseline: UTC DATETIME(6), explicit FK constraints, deterministic collation.
CREATE TABLE audit_event (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id     VARCHAR(64) NOT NULL,
    event_type VARCHAR(48) NOT NULL,
    at         DATETIME(6) NOT NULL,
    detail     VARCHAR(1024),
    trace_id   VARCHAR(64)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;

CREATE INDEX idx_audit_event_run ON audit_event (run_id, at);
